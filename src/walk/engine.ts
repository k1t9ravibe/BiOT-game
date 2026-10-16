import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'

/**
 * Движок режима ходьбы: загружает сцену из Blender (.glb), персонажа, управляет камерой от третьего лица.
 * Роли объектов берутся из имён в .glb (см. blender/build_t1.py):
 *   item_<id> — можно осмотреть (свойство inspect_range — свой радиус осмотра, м); к одному объекту можно привязать
 *   несколько карточек: item_<id1>+<id2>, wall_* или свойство solid — препятствие,
 *   spawn_A / goal_B — точки маршрута, walk_min / walk_max — углы зоны, где можно ходить (по умолчанию ±24 м).
 */

/** Настройки сцены; без них движок работает как в сцене 1 */
export interface WalkOptions {
  /** Туман: где начинается и где всё скрывается, м */
  fog?: [number, number]
  /** Дальность прорисовки камеры, м */
  far?: number
  /** Солнце и тени следуют за игроком — для сцен больше квадрата 50×50 м */
  sunFollow?: boolean
  /** «Живые» детали сцены: создаются после загрузки, update вызывается каждый кадр */
  ambient?: (root: THREE.Object3D, scene: THREE.Scene) => { update: (dt: number, t: number) => void }
}

export interface EngineCallbacks {
  /** id объектов в радиусе осмотра, ближайший первым */
  onNear: (ids: string[]) => void
  /** Расстояние до точки B, м */
  onDistB: (d: number) => void
  /** Нажата клавиша осмотра (E) */
  onInspectKey: () => void
  onReady: () => void
  onError: (msg: string) => void
}

interface Inspectable {
  id: string
  obj: THREE.Object3D
  box: THREE.Box3
  mats: THREE.MeshStandardMaterial[]
  marker?: THREE.Sprite
  /** Радиус осмотра, м */
  range: number
}

const INSPECT_RANGE = 2.2
const PLAYER_RADIUS = 0.35
const WALK_SPEED = 3.2
const RUN_SPEED = 5.5
const WORLD_LIMIT = 24

export class WalkEngine {
  private renderer: THREE.WebGLRenderer
  private scene = new THREE.Scene()
  private camera = new THREE.PerspectiveCamera(55, 1, 0.1, 200)
  private clock = new THREE.Clock()
  private raf = 0
  private ro: ResizeObserver
  private player = new THREE.Group()
  private limbs: Record<string, THREE.Object3D> = {}
  private colliders: THREE.Box3[] = []
  private items: Inspectable[] = []
  private goal = new THREE.Vector3()
  private goalRing?: THREE.Mesh
  private labelA?: THREE.Sprite
  private spawn = new THREE.Vector3()
  private keys = new Set<string>()
  private stick = { x: 0, y: 0 }
  private yaw = 0
  private camDist = 6.5
  private phase = 0
  private paused = false
  private lastNear = ''
  private lastDist = -1
  private highlighted = new Set<string>()
  private disposed = false
  private container: HTMLElement
  private cb: EngineCallbacks
  private opts: WalkOptions
  private sun = new THREE.DirectionalLight('#fff4e0', 2.4)
  private bounds = { minX: -WORLD_LIMIT, maxX: WORLD_LIMIT, minZ: -WORLD_LIMIT, maxZ: WORLD_LIMIT }
  private ambient?: { update: (dt: number, t: number) => void }

  constructor(container: HTMLElement, sceneUrl: string, workerUrl: string, cb: EngineCallbacks, opts: WalkOptions = {}) {
    this.container = container
    this.cb = cb
    this.opts = opts
    this.camera.far = opts.far ?? 200
    this.camera.updateProjectionMatrix()
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    this.renderer.shadowMap.enabled = true
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping
    this.renderer.domElement.style.touchAction = 'none'
    container.appendChild(this.renderer.domElement)

    // Небо, туман у горизонта, свет
    this.scene.background = new THREE.Color('#a9d6f5')
    const [fogNear, fogFar] = opts.fog ?? [30, 70]
    this.scene.fog = new THREE.Fog('#cfe6f5', fogNear, fogFar)
    this.scene.add(new THREE.HemisphereLight('#dff1ff', '#8a9a5b', 1.6))
    const sun = this.sun
    sun.position.set(12, 20, 8)
    sun.castShadow = true
    sun.shadow.mapSize.set(2048, 2048)
    Object.assign(sun.shadow.camera, { left: -25, right: 25, top: 25, bottom: -25, near: 1, far: 60 })
    sun.shadow.bias = -0.0005
    this.scene.add(sun, sun.target)

    this.ro = new ResizeObserver(() => this.resize())
    this.ro.observe(container)
    this.resize()
    this.bindInput()
    this.load(sceneUrl, workerUrl)
  }

  private async load(sceneUrl: string, workerUrl: string) {
    try {
      const loader = new GLTFLoader()
      const [world, worker] = await Promise.all([loader.loadAsync(sceneUrl), loader.loadAsync(workerUrl)])
      if (this.disposed) return
      this.setupWorld(world.scene)
      this.setupPlayer(worker.scene)
      this.ambient = this.opts.ambient?.(world.scene, this.scene)
      this.cb.onReady()
      this.loop()
    } catch (e) {
      this.cb.onError((e as Error).message)
    }
  }

  private setupWorld(root: THREE.Object3D) {
    this.scene.add(root)
    root.updateMatrixWorld(true)
    root.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) {
        o.castShadow = o.name !== 'ground'
        o.receiveShadow = true
      }
    })

    // Зона, где можно ходить: пустышки walk_min / walk_max (оси Blender X/Y → three X/−Z)
    const wmin = root.getObjectByName('walk_min')?.position
    const wmax = root.getObjectByName('walk_max')?.position
    if (wmin && wmax) {
      this.bounds = {
        minX: Math.min(wmin.x, wmax.x),
        maxX: Math.max(wmin.x, wmax.x),
        minZ: Math.min(wmin.z, wmax.z),
        maxZ: Math.max(wmin.z, wmax.z),
      }
    }

    let spawn = new THREE.Vector3()
    for (const o of [...root.children]) {
      const name = o.name
      if (name === 'spawn_A') spawn = o.getWorldPosition(new THREE.Vector3())
      else if (name === 'goal_B') this.goal = o.getWorldPosition(new THREE.Vector3())

      if (name.startsWith('wall_') || o.userData.solid) {
        this.colliders.push(new THREE.Box3().setFromObject(o).expandByScalar(PLAYER_RADIUS))
      }
      if (name.startsWith('item_')) {
        // Материалы клонируем, чтобы подсветка одного объекта не красила другие с тем же материалом
        const mats: THREE.MeshStandardMaterial[] = []
        o.traverse((m) => {
          const mesh = m as THREE.Mesh
          if (!mesh.isMesh) return
          const cloned = (Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map((x) => x.clone() as THREE.MeshStandardMaterial)
          mesh.material = Array.isArray(mesh.material) ? cloned : cloned[0]
          mats.push(...cloned)
        })
        const range = Number(o.userData.inspect_range) || INSPECT_RANGE
        const box = new THREE.Box3().setFromObject(o)
        for (const id of name.slice(5).split('+')) this.items.push({ id, obj: o, box, mats, range })
      }
    }

    // Отметки точек A и B на земле
    this.spawn.copy(spawn)
    this.labelA = this.groundLabel(spawn, 'A', '#0B2A5B')
    this.scene.add(this.labelA)
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.9, 1.2, 40),
      new THREE.MeshBasicMaterial({ color: '#1E6BFF', transparent: true, opacity: 0.8, side: THREE.DoubleSide }),
    )
    ring.rotation.x = -Math.PI / 2
    ring.position.copy(this.goal).setY(0.03)
    this.goalRing = ring
    this.scene.add(ring, this.groundLabel(this.goal, 'B', '#1E6BFF'))

    this.player.position.copy(spawn).setY(0)
    // Камера за спиной игрока, лицом в сторону точки B
    const heading = Math.atan2(this.goal.x - spawn.x, this.goal.z - spawn.z)
    this.player.rotation.y = heading
    this.yaw = heading + Math.PI
  }

  private setupPlayer(model: THREE.Object3D) {
    model.traverse((o) => {
      if ((o as THREE.Mesh).isMesh) o.castShadow = true
      if (/^(leg|arm)_[LR]$/.test(o.name)) this.limbs[o.name] = o
    })
    this.player.add(model)
    this.scene.add(this.player)
    this.updateCamera(1)
  }

  private groundLabel(pos: THREE.Vector3, text: string, color: string) {
    const s = this.makeSprite(text, color, 128)
    s.position.copy(pos).setY(2.6)
    s.scale.set(0.9, 0.9, 1)
    return s
  }

  /** Круглая подпись (номер отметки, буква точки) */
  private makeSprite(text: string, color: string, size = 128) {
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
    return new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }))
  }

  // ---------- Ввод ----------

  private onKeyDown = (e: KeyboardEvent) => {
    if ((e.target as HTMLElement).closest('input, textarea, select')) return
    const k = e.code
    if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ShiftLeft', 'ShiftRight'].includes(k)) {
      this.keys.add(k)
      e.preventDefault()
    }
    if (k === 'KeyE' && !e.repeat && !this.paused) this.cb.onInspectKey()
  }
  private onKeyUp = (e: KeyboardEvent) => this.keys.delete(e.code)
  private onBlur = () => this.keys.clear()

  // Поворот камеры перетаскиванием мыши / пальца по сцене, зум колесом
  private dragId: number | null = null
  private dragX = 0
  private onPointerDown = (e: PointerEvent) => {
    this.dragId = e.pointerId
    this.dragX = e.clientX
    this.renderer.domElement.setPointerCapture(e.pointerId)
  }
  private onPointerMove = (e: PointerEvent) => {
    if (e.pointerId !== this.dragId) return
    this.yaw -= (e.clientX - this.dragX) * 0.006
    this.dragX = e.clientX
  }
  private onPointerUp = (e: PointerEvent) => {
    if (e.pointerId === this.dragId) this.dragId = null
  }
  private onWheel = (e: WheelEvent) => {
    e.preventDefault()
    this.camDist = THREE.MathUtils.clamp(this.camDist + e.deltaY * 0.005, 3.5, 11)
  }

  private bindInput() {
    window.addEventListener('keydown', this.onKeyDown)
    window.addEventListener('keyup', this.onKeyUp)
    window.addEventListener('blur', this.onBlur)
    const el = this.renderer.domElement
    el.addEventListener('pointerdown', this.onPointerDown)
    el.addEventListener('pointermove', this.onPointerMove)
    el.addEventListener('pointerup', this.onPointerUp)
    el.addEventListener('pointercancel', this.onPointerUp)
    el.addEventListener('wheel', this.onWheel, { passive: false })
  }

  /** Экранный джойстик: x вправо, y вперёд, значения −1..1 */
  setStick(x: number, y: number) {
    this.stick = { x, y }
  }

  setPaused(p: boolean) {
    this.paused = p
    if (p) this.keys.clear()
  }

  /** Номера над отмеченными объектами */
  setMarked(ids: string[]) {
    // Если у объекта отмечено несколько карточек, номера встают столбиком
    const stacked = new Map<THREE.Object3D, number>()
    for (const it of this.items) {
      const n = ids.indexOf(it.id)
      if (it.marker) {
        this.scene.remove(it.marker)
        it.marker.material.map?.dispose()
        it.marker.material.dispose()
        it.marker = undefined
      }
      if (n >= 0) {
        const s = this.makeSprite(String(n + 1), '#1E6BFF')
        const c = it.box.getCenter(new THREE.Vector3())
        const k = stacked.get(it.obj) ?? 0
        stacked.set(it.obj, k + 1)
        s.position.set(c.x, it.box.max.y + 0.5 + k * 0.7, c.z)
        s.scale.set(0.6, 0.6, 1)
        it.marker = s
        this.scene.add(s)
      }
    }
  }

  // ---------- Игровой цикл ----------

  private loop = () => {
    this.raf = requestAnimationFrame(this.loop)
    const dt = Math.min(this.clock.getDelta(), 0.05)
    if (!this.paused) this.updatePlayer(dt)
    this.updateCamera(dt)
    if (this.opts.sunFollow) {
      const p = this.player.position
      this.sun.position.set(p.x + 12, 20, p.z + 8)
      this.sun.target.position.copy(p)
    }
    this.ambient?.update(dt, this.clock.elapsedTime)
    this.updateProximity()
    // Метку A прячем, когда игрок отошёл от старта, — иначе камера проходит сквозь неё
    if (this.labelA) this.labelA.visible = this.player.position.distanceTo(this.spawn) < 1.5
    if (this.goalRing) {
      const t = this.clock.elapsedTime
      this.goalRing.scale.setScalar(1 + Math.sin(t * 3) * 0.08)
    }
    this.renderer.render(this.scene, this.camera)
  }

  private updatePlayer(dt: number) {
    const k = this.keys
    let ix = this.stick.x + (k.has('KeyD') || k.has('ArrowRight') ? 1 : 0) - (k.has('KeyA') || k.has('ArrowLeft') ? 1 : 0)
    let iy = this.stick.y + (k.has('KeyW') || k.has('ArrowUp') ? 1 : 0) - (k.has('KeyS') || k.has('ArrowDown') ? 1 : 0)
    const len = Math.hypot(ix, iy)
    if (len > 1) {
      ix /= len
      iy /= len
    }

    // Направления относительно камеры
    const fwd = new THREE.Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw))
    const right = new THREE.Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw))
    const move = fwd.multiplyScalar(iy).add(right.multiplyScalar(ix))
    const amount = Math.min(1, move.length())
    const speed = (k.has('ShiftLeft') || k.has('ShiftRight') ? RUN_SPEED : WALK_SPEED) * amount

    if (amount > 0.05) {
      move.normalize()
      const p = this.player.position
      // Сдвиг по осям по отдельности — так игрок «скользит» вдоль стен
      const b = this.bounds
      const nx = THREE.MathUtils.clamp(p.x + move.x * speed * dt, b.minX, b.maxX)
      if (!this.blocked(nx, p.z)) p.x = nx
      const nz = THREE.MathUtils.clamp(p.z + move.z * speed * dt, b.minZ, b.maxZ)
      if (!this.blocked(p.x, nz)) p.z = nz

      // Плавный поворот в сторону движения
      const target = Math.atan2(move.x, move.z)
      let diff = target - this.player.rotation.y
      diff = Math.atan2(Math.sin(diff), Math.cos(diff))
      this.player.rotation.y += diff * Math.min(1, dt * 12)
      this.phase += dt * speed * 2.4
    } else {
      this.phase *= 0.85
    }

    // Анимация шага: ноги и руки качаются в противофазе
    const swing = Math.sin(this.phase) * (amount > 0.05 ? 0.55 : 0)
    const ease = (o: THREE.Object3D | undefined, v: number) => o && (o.rotation.x += (v - o.rotation.x) * Math.min(1, dt * 14))
    ease(this.limbs.leg_L, swing)
    ease(this.limbs.leg_R, -swing)
    ease(this.limbs.arm_L, -swing * 0.8)
    ease(this.limbs.arm_R, swing * 0.8)
  }

  private blocked(x: number, z: number) {
    for (const b of this.colliders) {
      if (x > b.min.x && x < b.max.x && z > b.min.z && z < b.max.z && b.min.y < 1.6) return true
    }
    return false
  }

  private updateCamera(dt: number) {
    const p = this.player.position
    const target = new THREE.Vector3(p.x + Math.sin(this.yaw) * this.camDist, p.y + 3.2, p.z + Math.cos(this.yaw) * this.camDist)
    this.camera.position.lerp(target, Math.min(1, dt * 6))
    this.camera.lookAt(p.x, p.y + 1.3, p.z)
  }

  private updateProximity() {
    const p = this.player.position
    const near = this.items
      .map((it) => {
        const dx = Math.max(it.box.min.x - p.x, 0, p.x - it.box.max.x)
        const dz = Math.max(it.box.min.z - p.z, 0, p.z - it.box.max.z)
        return { it, d: Math.hypot(dx, dz) }
      })
      .filter((x) => x.d < x.it.range)
      .sort((a, b) => a.d - b.d)
      .map((x) => x.it.id)

    const key = near.join('|')
    if (key !== this.lastNear) {
      this.lastNear = key
      // Подсвечиваем объекты рядом с игроком
      for (const it of this.items) {
        const on = near.includes(it.id)
        if (on === this.highlighted.has(it.id)) continue
        for (const m of it.mats) m.emissive.set(on ? '#1E6BFF' : '#000000').multiplyScalar(on ? 0.25 : 0)
        if (on) this.highlighted.add(it.id)
        else this.highlighted.delete(it.id)
      }
      this.cb.onNear(near)
    }

    const d = Math.round(Math.hypot(this.goal.x - p.x, this.goal.z - p.z) * 2) / 2
    if (d !== this.lastDist) {
      this.lastDist = d
      this.cb.onDistB(d)
    }
  }

  private resize() {
    const w = this.container.clientWidth
    const h = this.container.clientHeight
    if (!w || !h) return
    this.renderer.setSize(w, h)
    this.camera.aspect = w / h
    this.camera.updateProjectionMatrix()
  }

  dispose() {
    this.disposed = true
    cancelAnimationFrame(this.raf)
    this.ro.disconnect()
    window.removeEventListener('keydown', this.onKeyDown)
    window.removeEventListener('keyup', this.onKeyUp)
    window.removeEventListener('blur', this.onBlur)
    this.scene.traverse((o) => {
      const m = o as THREE.Mesh
      m.geometry?.dispose()
      const mats = Array.isArray(m.material) ? m.material : m.material ? [m.material] : []
      for (const x of mats) {
        ;(x as THREE.SpriteMaterial).map?.dispose()
        x.dispose()
      }
    })
    this.renderer.dispose()
    this.renderer.domElement.remove()
  }
}
