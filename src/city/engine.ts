import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

/**
 * Движок локации 2 «Город»: улица сбоку с горизонтальной прокруткой. Сцена — из blender/build_city.py.
 * Параллакс получается сам: камера смещается по X, а слои стоят на разной глубине
 * (тротуар и дорога → здания → дома среднего плана → силуэты высоток и облака).
 * Имена объектов в .glb описаны в шапке build_city.py.
 */

export interface CityCallbacks {
  onReady: () => void
  onError: (msg: string) => void
  /** Нажали на здание или его метку */
  onSelect: (id: string) => void
  /** Здание под курсором (null — ни одного) */
  onHover: (id: string | null) => void
}

interface Building {
  id: string
  meshes: THREE.Object3D[]
  mats: THREE.MeshStandardMaterial[]
  /** Собственное свечение материалов из сцены — подсветка добавляется к нему и потом возвращает его */
  glow: THREE.Color[]
  pin: THREE.Sprite
  pinBase: THREE.Vector3
  x: number
  num: number
}

interface Mover {
  obj: THREE.Object3D
  x: number
  dir: 1 | -1
  speed: number
  want: number
  len: number
  limbs: { node: THREE.Object3D; k: number }[]
  phase: number
}

interface Puff {
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>
  age: number
  life: number
  vx: number
}

const SKY = '#a9d6f5'
const FOG = '#cfe6f5'
const ACCENT = '#1E6BFF'
const DONE = '#16A34A'
/** Машины и пешеходы ходят по кругу в этих пределах по X — края за кадром */
const LOOP_MIN = -80
const LOOP_MAX = 260
const CAR_COLORS = ['#D64541', '#F4F5F2', '#2F6FB8', '#3A3F45', '#C9CDD2', '#4F8A2E', '#E0A33A', '#8E3E3E']

export class CityEngine {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(42, 1, 0.5, 900)
  private sun = new THREE.DirectionalLight('#fff4e0', 2.4)
  private clock = new THREE.Clock()
  private raf = 0
  private ro: ResizeObserver
  private container: HTMLElement
  private cb: CityCallbacks
  private disposed = false

  private camX = 0
  private camTarget = 0
  private camMin = 0
  private camMax = 100

  private buildings: Building[] = []
  private meshToBuilding = new Map<THREE.Object3D, Building>()
  private cars: Mover[] = []
  private peds: Mover[] = []
  private blinkers: { mat: THREE.MeshStandardMaterial; timer: number; on: boolean; level: number }[] = []
  private slew?: THREE.Object3D
  private trolley?: THREE.Object3D
  private trolleyX0 = 0
  private smokeSrc?: THREE.Vector3
  private puffs: Puff[] = []
  private smokeTimer = 0
  private puffGeo = new THREE.IcosahedronGeometry(1, 0)
  private clouds: { obj: THREE.Object3D; speed: number }[] = []

  private raycaster = new THREE.Raycaster()
  private pointer = new THREE.Vector2()
  private pointerMoved = false
  private hoverId: string | null = null
  private highlight = new THREE.Color(ACCENT).multiplyScalar(0.22)
  private inputEnabled = true
  private keys = new Set<string>()
  private drag: { id: number; startX: number; lastX: number; moved: boolean } | null = null

  constructor(container: HTMLElement, url: string, cb: CityCallbacks) {
    this.container = container
    this.cb = cb
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.domElement.style.touchAction = 'none'
    container.appendChild(this.renderer.domElement)

    // Небо, дымка у горизонта, свет — как в локации 1
    this.scene.background = new THREE.Color(SKY)
    this.scene.fog = new THREE.Fog(FOG, 90, 330)
    this.scene.add(new THREE.HemisphereLight('#dff1ff', '#8a9a5b', 1.6))
    this.sun.castShadow = true
    this.sun.shadow.mapSize.set(2048, 2048)
    Object.assign(this.sun.shadow.camera, { left: -60, right: 60, top: 45, bottom: -45, near: 1, far: 160 })
    this.sun.shadow.bias = -0.0006
    this.scene.add(this.sun, this.sun.target)

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(container)
    this.resize()
    this.bindInput()
    this.load(url)
  }

  // ---------- Загрузка ----------

  private async load(url: string) {
    try {
      const gltf = await new GLTFLoader().loadAsync(url)
      if (this.disposed) return
      this.setup(gltf.scene)
      this.cb.onReady()
      this.loop()
    } catch (e) {
      this.cb.onError((e as Error).message)
    }
  }

  private setup(root: THREE.Object3D) {
    this.scene.add(root)
    root.updateMatrixWorld(true)
    const noShadow = new Set(['ground', 'street', 'city_skyline', 'city_mid_blocks'])
    for (const top of root.children) {
      top.traverse((o) => {
        if ((o as THREE.Mesh).isMesh) {
          o.castShadow = !noShadow.has(top.name)
          o.receiveShadow = true
        }
      })
    }

    const find = (name: string) => root.getObjectByName(name)
    const zOf = (name: string, fallback: number) => find(name)?.position.z ?? fallback
    this.camMin = find('cam_min')?.position.x ?? 20
    this.camMax = find('cam_max')?.position.x ?? 160
    this.camX = this.camTarget = this.camMin

    // Мигающие окна: у каждого свой материал
    root.traverse((o) => {
      if (!o.name.startsWith('win_') || !(o as THREE.Mesh).isMesh) return
      const mesh = o as THREE.Mesh
      const mat = (mesh.material as THREE.MeshStandardMaterial).clone()
      mesh.material = mat
      this.blinkers.push({ mat, timer: 1 + Math.random() * 8, on: false, level: 0 })
    })

    // Здания-организации: метка, подсветка, клик
    const order = root.children.filter((o) => o.name.startsWith('bld_'))
    const withX = order.map((o) => ({ o, id: o.name.slice(4), spot: find(`spot_${o.name.slice(4)}`) }))
    withX.sort((a, b) => (a.spot?.position.x ?? 0) - (b.spot?.position.x ?? 0))
    withX.forEach(({ o, id, spot }, i) => {
      const meshes: THREE.Object3D[] = []
      const mats: THREE.MeshStandardMaterial[] = []
      o.traverse((m) => {
        const mesh = m as THREE.Mesh
        if (!mesh.isMesh || m.name.startsWith('win_')) return
        const cloned = (mesh.material as THREE.MeshStandardMaterial).clone()
        mesh.material = cloned
        mats.push(cloned)
        meshes.push(mesh)
      })
      const pinBase = spot ? spot.getWorldPosition(new THREE.Vector3()) : new THREE.Vector3()
      const pin = this.makePin(String(i + 1), ACCENT)
      pin.position.copy(pinBase)
      this.scene.add(pin)
      const glow = mats.map((m) => m.emissive.clone())
      const b: Building = { id, meshes, mats, glow, pin, pinBase, x: pinBase.x, num: i + 1 }
      this.buildings.push(b)
      for (const m of meshes) this.meshToBuilding.set(m, b)
      this.meshToBuilding.set(pin, b)
    })

    // Кран и труба
    this.slew = find('crane_slew')
    this.trolley = find('crane_trolley')
    this.trolleyX0 = this.trolley?.position.x ?? 0
    this.smokeSrc = find('smoke_src')?.getWorldPosition(new THREE.Vector3())

    // Образцы машин и пешеходов убираем из сцены и клонируем на полосы и тротуары
    const tpl = (prefix: string) => root.children.filter((o) => o.name.startsWith(prefix))
    const carTpl = tpl('car_tpl_')
    const pedTpl = tpl('ped_tpl_')
    for (const t of [...carTpl, ...pedTpl]) root.remove(t)
    this.spawnCars(carTpl, zOf('lane_near', 1), zOf('lane_far', -3))
    this.spawnPeds(pedTpl, zOf('walk_near', 4.6), zOf('walk_far', -6))
    this.spawnClouds()
  }

  private spawnCars(tpl: THREE.Object3D[], zNear: number, zFar: number) {
    if (!tpl.length) return
    const byKind = (k: string) => tpl.find((t) => t.name.endsWith(k)) ?? tpl[0]
    const pool = ['sedan', 'sedan', 'sedan', 'hatch', 'hatch', 'bus', 'truck']
    for (const [z, dir] of [[zNear, 1], [zFar, -1]] as const) {
      const n = 7
      for (let k = 0; k < n; k++) {
        const kind = pool[(k * 3 + (dir > 0 ? 0 : 2)) % pool.length]
        const obj = byKind(kind).clone()
        obj.traverse((m) => {
          const mesh = m as THREE.Mesh
          if (!mesh.isMesh) return
          const mat = mesh.material as THREE.MeshStandardMaterial
          if (mat.name === 'Кузов авто') {
            const c = mat.clone()
            c.color.set(CAR_COLORS[Math.floor(Math.random() * CAR_COLORS.length)])
            mesh.material = c
          }
        })
        const x = LOOP_MIN + (k + Math.random() * 0.5) * ((LOOP_MAX - LOOP_MIN) / n)
        obj.position.set(x, 0, z)
        obj.rotation.y = dir > 0 ? 0 : Math.PI
        this.scene.add(obj)
        const len = kind === 'bus' ? 11 : kind === 'truck' ? 7.2 : 4.5
        const want = kind === 'bus' ? 6.5 : kind === 'truck' ? 7.5 : 8 + Math.random() * 4
        this.cars.push({ obj, x, dir, speed: want, want, len, limbs: [], phase: 0 })
      }
    }
  }

  private spawnPeds(tpl: THREE.Object3D[], zNear: number, zFar: number) {
    if (!tpl.length) return
    for (const z of [zNear, zFar]) {
      for (let k = 0; k < 8; k++) {
        const obj = tpl[(k + (z === zNear ? 0 : 1)) % tpl.length].clone()
        const dir: 1 | -1 = Math.random() < 0.5 ? 1 : -1
        const x = LOOP_MIN + Math.random() * (LOOP_MAX - LOOP_MIN)
        obj.position.set(x, 0, z + (Math.random() - 0.5) * 1.2)
        obj.rotation.y = dir > 0 ? 0 : Math.PI
        const limbs: Mover['limbs'] = []
        obj.traverse((m) => {
          // Только сам узел конечности: его части-меши называются …_leg_L_1 и вращаются вместе с ним
          const r = /_(leg|arm)_([LR])$/.exec(m.name)
          if (r) limbs.push({ node: m, k: (r[1] === 'leg' ? 1 : -0.8) * (r[2] === 'L' ? 1 : -1) })
        })
        this.scene.add(obj)
        const want = 1.0 + Math.random() * 0.6
        this.peds.push({ obj, x, dir, speed: want, want, len: 0.6, limbs, phase: Math.random() * 6 })
      }
    }
  }

  private spawnClouds() {
    // Облака светятся сами — иначе снизу они серые, как камни
    const mat = new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: '#ffffff', emissiveIntensity: 0.6, flatShading: true, roughness: 1, fog: false })
    for (let k = 0; k < 11; k++) {
      const g = new THREE.Group()
      const parts = 4 + Math.floor(Math.random() * 3)
      for (let i = 0; i < parts; i++) {
        const m = new THREE.Mesh(this.puffGeo, mat)
        const r = 5 + Math.random() * 6
        m.scale.set(r * 1.3, r * 0.75, r)
        m.position.set(i * 7 - parts * 3.5 + Math.random() * 3, Math.random() * 3, Math.random() * 4)
        g.add(m)
      }
      g.position.set(-150 + k * 50 + Math.random() * 25, 110 + Math.random() * 35, -260 - Math.random() * 60)
      this.scene.add(g)
      this.clouds.push({ obj: g, speed: 1.2 + Math.random() * 1.8 })
    }
  }

  /** Круглая метка с номером здания или галочкой */
  private makePin(text: string, color: string) {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.pinTexture(text, color), depthTest: false }))
    s.scale.set(2.6, 2.6, 1)
    s.renderOrder = 10
    return s
  }

  private pinTexture(text: string, color: string) {
    const size = 128
    const c = document.createElement('canvas')
    c.width = c.height = size
    const g = c.getContext('2d')!
    g.fillStyle = color
    g.beginPath()
    g.arc(size / 2, size / 2, size / 2 - 6, 0, Math.PI * 2)
    g.fill()
    g.lineWidth = 8
    g.strokeStyle = '#fff'
    g.stroke()
    g.fillStyle = '#fff'
    g.font = `bold ${size * 0.5}px Inter, sans-serif`
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(text, size / 2, size / 2 + size * 0.03)
    const tex = new THREE.CanvasTexture(c)
    tex.colorSpace = THREE.SRGBColorSpace
    return tex
  }

  // ---------- Управление извне ----------

  /** Отмечает пройденные здания зелёной галочкой */
  setDone(ids: string[]) {
    for (const b of this.buildings) {
      const done = ids.includes(b.id)
      const mat = b.pin.material
      mat.map?.dispose()
      mat.map = this.pinTexture(done ? '✓' : String(b.num), done ? DONE : ACCENT)
      mat.needsUpdate = true
    }
  }

  /** Прокручивает улицу к зданию */
  focus(id: string) {
    const b = this.buildings.find((x) => x.id === id)
    if (b) this.camTarget = THREE.MathUtils.clamp(b.x, this.camMin, this.camMax)
  }

  scrollBy(dx: number) {
    this.camTarget = THREE.MathUtils.clamp(this.camTarget + dx, this.camMin, this.camMax)
  }

  /** Пока открыто окно с вопросами, сцена живёт, но на ввод не реагирует */
  setInputEnabled(on: boolean) {
    this.inputEnabled = on
    if (!on) {
      this.keys.clear()
      this.drag = null
      this.setHover(null)
    }
  }

  // ---------- Ввод ----------

  private onPointerDown = (e: PointerEvent) => {
    if (!this.inputEnabled) return
    this.drag = { id: e.pointerId, startX: e.clientX, lastX: e.clientX, moved: false }
    this.renderer.domElement.setPointerCapture(e.pointerId)
  }

  private onPointerMove = (e: PointerEvent) => {
    const r = this.renderer.domElement.getBoundingClientRect()
    this.pointer.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1)
    this.pointerMoved = true
    if (!this.drag || e.pointerId !== this.drag.id) return
    const dx = e.clientX - this.drag.lastX
    this.drag.lastX = e.clientX
    if (Math.abs(e.clientX - this.drag.startX) > 6) this.drag.moved = true
    this.scrollBy(-dx * this.worldPerPixel())
  }

  private onPointerUp = (e: PointerEvent) => {
    if (!this.drag || e.pointerId !== this.drag.id) return
    const click = !this.drag.moved
    this.drag = null
    if (click && this.inputEnabled) {
      const b = this.pick()
      if (b) this.cb.onSelect(b.id)
    }
  }

  private onPointerLeave = () => this.setHover(null)

  private onWheel = (e: WheelEvent) => {
    e.preventDefault()
    if (!this.inputEnabled) return
    const d = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY
    this.scrollBy(d * 0.06)
  }

  private onKeyDown = (e: KeyboardEvent) => {
    if (!this.inputEnabled || (e.target as HTMLElement).closest('input, textarea, select')) return
    if (['ArrowLeft', 'ArrowRight', 'KeyA', 'KeyD'].includes(e.code)) {
      this.keys.add(e.code)
      e.preventDefault()
    }
  }
  private onKeyUp = (e: KeyboardEvent) => this.keys.delete(e.code)
  private onBlur = () => this.keys.clear()

  private bindInput() {
    const el = this.renderer.domElement
    el.addEventListener('pointerdown', this.onPointerDown)
    el.addEventListener('pointermove', this.onPointerMove)
    el.addEventListener('pointerup', this.onPointerUp)
    el.addEventListener('pointercancel', this.onPointerUp)
    el.addEventListener('pointerleave', this.onPointerLeave)
    el.addEventListener('wheel', this.onWheel, { passive: false })
    window.addEventListener('keydown', this.onKeyDown)
    window.addEventListener('keyup', this.onKeyUp)
    window.addEventListener('blur', this.onBlur)
  }

  /** Сколько метров улицы приходится на пиксель экрана на глубине зданий */
  private worldPerPixel() {
    const dist = 52
    const h = 2 * dist * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2))
    return (h * this.camera.aspect) / Math.max(1, this.container.clientWidth)
  }

  private pick(): Building | null {
    this.raycaster.setFromCamera(this.pointer, this.camera)
    const pins = this.raycaster.intersectObjects(this.buildings.map((b) => b.pin), false)
    if (pins.length) return this.meshToBuilding.get(pins[0].object) ?? null
    const hits = this.raycaster.intersectObjects(this.buildings.flatMap((b) => b.meshes), false)
    return hits.length ? (this.meshToBuilding.get(hits[0].object) ?? null) : null
  }

  private setHover(id: string | null) {
    if (id === this.hoverId) return
    this.hoverId = id
    for (const b of this.buildings) {
      const on = b.id === id
      b.mats.forEach((m, k) => {
        m.emissive.copy(b.glow[k])
        if (on) m.emissive.add(this.highlight)
      })
    }
    this.renderer.domElement.style.cursor = id ? 'pointer' : 'grab'
    this.cb.onHover(id)
  }

  // ---------- Игровой цикл ----------

  private loop = () => {
    this.raf = requestAnimationFrame(this.loop)
    const dt = Math.min(this.clock.getDelta(), 0.05)
    const t = this.clock.elapsedTime

    // Камера: клавиши, плавное догоняние цели
    const kd = (this.keys.has('ArrowRight') || this.keys.has('KeyD') ? 1 : 0) - (this.keys.has('ArrowLeft') || this.keys.has('KeyA') ? 1 : 0)
    if (kd) this.scrollBy(kd * 30 * dt)
    this.camX += (this.camTarget - this.camX) * Math.min(1, dt * 6)
    this.camera.position.set(this.camX, 5.5, 40)
    this.camera.lookAt(this.camX, 12, -10)
    this.sun.position.set(this.camX + 25, 45, 35)
    this.sun.target.position.set(this.camX, 0, -10)

    if (this.pointerMoved && !this.drag && this.inputEnabled) {
      this.pointerMoved = false
      this.setHover(this.pick()?.id ?? null)
    }

    this.updateTraffic(dt)
    this.updatePeople(dt)
    this.updateBlink(dt)
    this.updateCrane(t)
    this.updateSmoke(dt)
    for (const c of this.clouds) {
      c.obj.position.x += c.speed * dt
      if (c.obj.position.x > 420) c.obj.position.x = -200
    }
    this.buildings.forEach((b, i) => b.pin.position.set(b.pinBase.x, b.pinBase.y + Math.sin(t * 2 + i) * 0.25, b.pinBase.z))

    this.renderer.render(this.scene, this.camera)
  }

  private updateTraffic(dt: number) {
    for (const dir of [1, -1] as const) {
      // Едущий впереди — первый; держим дистанцию до него
      const lane = this.cars.filter((c) => c.dir === dir).sort((a, b) => (b.x - a.x) * dir)
      lane.forEach((car, i) => {
        let target = car.want
        if (i > 0) {
          const ahead = lane[i - 1]
          const gap = (ahead.x - car.x) * dir - (ahead.len + car.len) / 2
          if (gap < 3) target = 0
          else if (gap < 10) target = Math.min(target, ahead.speed)
        }
        car.speed += (target - car.speed) * Math.min(1, dt * 2.5)
        car.x += dir * car.speed * dt
        if (dir > 0 && car.x > LOOP_MAX) car.x = LOOP_MIN
        if (dir < 0 && car.x < LOOP_MIN) car.x = LOOP_MAX
        car.obj.position.x = car.x
      })
    }
  }

  private updatePeople(dt: number) {
    for (const p of this.peds) {
      p.x += p.dir * p.speed * dt
      if (p.x > LOOP_MAX) p.x = LOOP_MIN
      if (p.x < LOOP_MIN) p.x = LOOP_MAX
      p.obj.position.x = p.x
      p.phase += dt * p.speed * 3.4
      const swing = Math.sin(p.phase) * 0.5
      for (const l of p.limbs) l.node.rotation.z = swing * l.k
    }
  }

  private updateBlink(dt: number) {
    for (const b of this.blinkers) {
      b.timer -= dt
      if (b.timer <= 0) {
        b.on = !b.on
        b.timer = b.on ? 0.4 + Math.random() * 1.2 : 3 + Math.random() * 8
      }
      b.level += ((b.on ? 1 : 0) - b.level) * Math.min(1, dt * 8)
      b.mat.emissive.setRGB(1, 0.92, 0.7).multiplyScalar(b.level * 0.9)
    }
  }

  private updateCrane(t: number) {
    if (this.slew) this.slew.rotation.y = Math.sin(t * 0.13) * 0.75
    if (this.trolley) this.trolley.position.x = this.trolleyX0 + Math.sin(t * 0.21 + 1) * 7
  }

  private updateSmoke(dt: number) {
    if (!this.smokeSrc) return
    this.smokeTimer -= dt
    if (this.smokeTimer <= 0) {
      this.smokeTimer = 0.35
      let p = this.puffs.find((x) => x.age >= x.life)
      if (!p) {
        const mat = new THREE.MeshStandardMaterial({ color: '#eceff1', flatShading: true, roughness: 1, transparent: true, depthWrite: false })
        p = { mesh: new THREE.Mesh(this.puffGeo, mat), age: 0, life: 7, vx: 0 }
        this.scene.add(p.mesh)
        this.puffs.push(p)
      }
      p.age = 0
      p.vx = 0.8 + Math.random() * 0.6
      p.mesh.position.copy(this.smokeSrc).add(new THREE.Vector3((Math.random() - 0.5) * 0.6, 0, (Math.random() - 0.5) * 0.6))
      p.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
      p.mesh.visible = true
    }
    for (const p of this.puffs) {
      if (p.age >= p.life) {
        p.mesh.visible = false
        continue
      }
      p.age += dt
      const k = p.age / p.life
      p.mesh.position.y += 1.8 * dt
      p.mesh.position.x += p.vx * dt
      p.mesh.scale.setScalar(0.8 + k * 3.2)
      p.mesh.material.opacity = 0.85 * Math.pow(1 - k, 1.2)
    }
  }

  private resize() {
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    if (!w || !h) return
    this.renderer.setSize(w, h)
    this.camera.aspect = w / h
    // На узком экране шире угол обзора, чтобы здания помещались по высоте
    this.camera.fov = this.camera.aspect < 1 ? 62 : this.camera.aspect < 1.4 ? 50 : 42
    this.camera.updateProjectionMatrix()
  }

  dispose() {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    const el = this.renderer.domElement
    el.removeEventListener('pointerdown', this.onPointerDown)
    el.removeEventListener('pointermove', this.onPointerMove)
    el.removeEventListener('pointerup', this.onPointerUp)
    el.removeEventListener('pointercancel', this.onPointerUp)
    el.removeEventListener('pointerleave', this.onPointerLeave)
    el.removeEventListener('wheel', this.onWheel)
    window.removeEventListener('keydown', this.onKeyDown)
    window.removeEventListener('keyup', this.onKeyUp)
    window.removeEventListener('blur', this.onBlur)
    this.renderer.dispose()
    el.remove()
  }
}
