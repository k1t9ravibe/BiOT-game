import * as THREE from 'three'

/**
 * «Живая улица» для сцены города (blender/build_city.py): машины на полосах, прохожие на дальнем тротуаре,
 * поблёскивающие окна, поворот башенного крана, дым из заводской трубы, облака.
 * Подключается к движку ходьбы через WalkOptions.ambient.
 */

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

/** Машины и прохожие ходят по кругу в этих пределах по X — края далеко за туманом */
const LOOP_MIN = -80
const LOOP_MAX = 260
const CAR_COLORS = ['#D64541', '#F4F5F2', '#2F6FB8', '#3A3F45', '#C9CDD2', '#4F8A2E', '#E0A33A', '#8E3E3E']

export function cityAmbient(root: THREE.Object3D, scene: THREE.Scene) {
  const find = (name: string) => root.getObjectByName(name)
  const zOf = (name: string, fallback: number) => find(name)?.position.z ?? fallback
  const puffGeo = new THREE.IcosahedronGeometry(1, 0)

  // Окна: у каждого свой материал, чтобы мигали вразнобой
  const blinkers: { mat: THREE.MeshStandardMaterial; timer: number; on: boolean; level: number }[] = []
  root.traverse((o) => {
    if (!o.name.startsWith('win_') || !(o as THREE.Mesh).isMesh) return
    const mesh = o as THREE.Mesh
    const mat = (mesh.material as THREE.MeshStandardMaterial).clone()
    mesh.material = mat
    blinkers.push({ mat, timer: 1 + Math.random() * 8, on: false, level: 0 })
  })

  const slew = find('crane_slew')
  const trolley = find('crane_trolley')
  const trolleyX0 = trolley?.position.x ?? 0
  const smokeSrc = find('smoke_src')?.getWorldPosition(new THREE.Vector3())

  // Образцы машин и прохожих убираем и клонируем на полосы и тротуар
  const tpl = (prefix: string) => root.children.filter((o) => o.name.startsWith(prefix))
  const carTpl = tpl('car_tpl_')
  const pedTpl = tpl('ped_tpl_')
  for (const t of [...carTpl, ...pedTpl]) root.remove(t)

  const cars: Mover[] = []
  if (carTpl.length) {
    const byKind = (k: string) => carTpl.find((t) => t.name.endsWith(k)) ?? carTpl[0]
    const pool = ['sedan', 'sedan', 'sedan', 'hatch', 'hatch', 'bus', 'truck']
    for (const [z, dir] of [[zOf('lane_near', 1), 1], [zOf('lane_far', -3), -1]] as const) {
      const n = 7
      for (let k = 0; k < n; k++) {
        const kind = pool[(k * 3 + (dir > 0 ? 0 : 2)) % pool.length]
        const obj = byKind(kind).clone()
        obj.traverse((m) => {
          const mesh = m as THREE.Mesh
          if (!mesh.isMesh) return
          mesh.castShadow = true
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
        scene.add(obj)
        const len = kind === 'bus' ? 11 : kind === 'truck' ? 7.2 : 4.5
        const want = kind === 'bus' ? 6.5 : kind === 'truck' ? 7.5 : 8 + Math.random() * 4
        cars.push({ obj, x, dir, speed: want, want, len, limbs: [], phase: 0 })
      }
    }
  }

  const peds: Mover[] = []
  const zWalk = zOf('walk_far', -6)
  for (let k = 0; pedTpl.length && k < 10; k++) {
    const obj = pedTpl[k % pedTpl.length].clone()
    const dir: 1 | -1 = Math.random() < 0.5 ? 1 : -1
    const x = LOOP_MIN + Math.random() * (LOOP_MAX - LOOP_MIN)
    obj.position.set(x, 0, zWalk + (Math.random() - 0.5) * 1.2)
    obj.rotation.y = dir > 0 ? 0 : Math.PI
    const limbs: Mover['limbs'] = []
    obj.traverse((m) => {
      if ((m as THREE.Mesh).isMesh) m.castShadow = true
      // Только сам узел конечности: его части-меши называются …_leg_L_1 и вращаются вместе с ним
      const r = /_(leg|arm)_([LR])$/.exec(m.name)
      if (r) limbs.push({ node: m, k: (r[1] === 'leg' ? 1 : -0.8) * (r[2] === 'L' ? 1 : -1) })
    })
    scene.add(obj)
    const want = 1.0 + Math.random() * 0.6
    peds.push({ obj, x, dir, speed: want, want, len: 0.6, limbs, phase: Math.random() * 6 })
  }

  // Облака светятся сами — иначе снизу они серые, как камни; туман их не трогает
  const clouds: { obj: THREE.Object3D; speed: number }[] = []
  const cloudMat = new THREE.MeshStandardMaterial({ color: '#ffffff', emissive: '#ffffff', emissiveIntensity: 0.6, flatShading: true, roughness: 1, fog: false })
  for (let k = 0; k < 16; k++) {
    const g = new THREE.Group()
    const parts = 4 + Math.floor(Math.random() * 3)
    for (let i = 0; i < parts; i++) {
      const m = new THREE.Mesh(puffGeo, cloudMat)
      const r = 5 + Math.random() * 6
      m.scale.set(r * 1.3, r * 0.75, r)
      m.position.set(i * 7 - parts * 3.5 + Math.random() * 3, Math.random() * 3, Math.random() * 4)
      g.add(m)
    }
    const side = k % 2 ? 1 : -1
    g.position.set(-150 + k * 34 + Math.random() * 25, 90 + Math.random() * 40, side * (240 + Math.random() * 80))
    scene.add(g)
    clouds.push({ obj: g, speed: 1.2 + Math.random() * 1.8 })
  }

  const puffs: Puff[] = []
  let smokeTimer = 0

  // Выхлоп бензинового генератора: сизые клубы сносит ветром к люку, и они уходят вниз, в колодец
  const exSrc = find('exhaust_src')?.getWorldPosition(new THREE.Vector3())
  const exTo = find('exhaust_to')?.getWorldPosition(new THREE.Vector3())
  const exhaust: { mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>; age: number }[] = []
  const EX_LIFE = 2.6
  let exTimer = 0
  function updateExhaust(dt: number) {
    if (!exSrc || !exTo) return
    exTimer -= dt
    if (exTimer <= 0) {
      exTimer = 0.18
      let p = exhaust.find((x) => x.age >= EX_LIFE)
      if (!p) {
        const mat = new THREE.MeshStandardMaterial({ color: '#7d848c', flatShading: true, roughness: 1, transparent: true, depthWrite: false })
        p = { mesh: new THREE.Mesh(puffGeo, mat), age: 0 }
        scene.add(p.mesh)
        exhaust.push(p)
      }
      p.age = 0
      p.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
      p.mesh.visible = true
    }
    for (const p of exhaust) {
      if (p.age >= EX_LIFE) {
        p.mesh.visible = false
        continue
      }
      p.age += dt
      const k = Math.min(1, p.age / EX_LIFE)
      // По дуге: сначала поднимается из трубы, потом опускается в люк
      p.mesh.position.lerpVectors(exSrc, exTo, k)
      p.mesh.position.y += Math.sin(k * Math.PI) * 0.35
      p.mesh.scale.setScalar(0.08 + Math.sin(k * Math.PI) * 0.22)
      p.mesh.material.opacity = 0.65 * Math.sin(Math.min(1, k * 1.2) * Math.PI)
    }
  }

  function updateTraffic(dt: number) {
    for (const dir of [1, -1] as const) {
      // Едущий впереди — первый; держим дистанцию до него
      const lane = cars.filter((c) => c.dir === dir).sort((a, b) => (b.x - a.x) * dir)
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

  function updatePeople(dt: number) {
    for (const p of peds) {
      p.x += p.dir * p.speed * dt
      if (p.x > LOOP_MAX) p.x = LOOP_MIN
      if (p.x < LOOP_MIN) p.x = LOOP_MAX
      p.obj.position.x = p.x
      p.phase += dt * p.speed * 3.4
      const swing = Math.sin(p.phase) * 0.5
      for (const l of p.limbs) l.node.rotation.z = swing * l.k
    }
  }

  function updateBlink(dt: number) {
    for (const b of blinkers) {
      b.timer -= dt
      if (b.timer <= 0) {
        b.on = !b.on
        b.timer = b.on ? 0.4 + Math.random() * 1.2 : 3 + Math.random() * 8
      }
      b.level += ((b.on ? 1 : 0) - b.level) * Math.min(1, dt * 8)
      b.mat.emissive.setRGB(1, 0.92, 0.7).multiplyScalar(b.level * 0.9)
    }
  }

  function updateSmoke(dt: number) {
    if (!smokeSrc) return
    smokeTimer -= dt
    if (smokeTimer <= 0) {
      smokeTimer = 0.35
      let p = puffs.find((x) => x.age >= x.life)
      if (!p) {
        const mat = new THREE.MeshStandardMaterial({ color: '#eceff1', flatShading: true, roughness: 1, transparent: true, depthWrite: false })
        p = { mesh: new THREE.Mesh(puffGeo, mat), age: 0, life: 7, vx: 0 }
        scene.add(p.mesh)
        puffs.push(p)
      }
      p.age = 0
      p.vx = 0.8 + Math.random() * 0.6
      p.mesh.position.copy(smokeSrc).add(new THREE.Vector3((Math.random() - 0.5) * 0.6, 0, (Math.random() - 0.5) * 0.6))
      p.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
      p.mesh.visible = true
    }
    for (const p of puffs) {
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

  return {
    update(dt: number, t: number) {
      updateTraffic(dt)
      updatePeople(dt)
      updateBlink(dt)
      if (slew) slew.rotation.y = Math.sin(t * 0.13) * 0.75
      if (trolley) trolley.position.x = trolleyX0 + Math.sin(t * 0.21 + 1) * 7
      updateSmoke(dt)
      updateExhaust(dt)
      for (const c of clouds) {
        c.obj.position.x += c.speed * dt
        if (c.obj.position.x > 420) c.obj.position.x = -200
      }
    },
  }
}
