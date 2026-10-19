import * as THREE from 'three'
import type { WalkSky } from '../walk/engine'

/**
 * Локация 4 «Серверная» (blender/build_server.py): помещение с окном. Днём в окно светит солнце,
 * рассеянный свет мягче уличного, потолочные светильники (пустышки lamp_<n>) горят холодным белым.
 * Из стойки, которую монтёр заливает водой, идёт дым (пустышки smoke_src_<n>): клубы поднимаются,
 * растут и бледнеют, под потолком растекаются в стороны.
 */

export const ROOM_SKY: WalkSky = {
  background: '#BFDDF2',
  fog: '#CFE6F5',
  hemi: ['#FFFFFF', '#C9CED6', 2.4],
  sun: ['#FFF1D6', 2.6, [4, 9, -14]], // со стороны окна (стена +Y в Blender — −z в игре)
}

const CEILING = 4
const SMOKE_EVERY = 0.12 // с, новый клуб из случайного источника
const SMOKE_LIFE = 6
const SMOKE_DARK = new THREE.Color('#3E4246') // у стойки дым тёмный, с возрастом светлеет
const SMOKE_LIGHT = new THREE.Color('#8E9399')

interface Puff {
  mesh: THREE.Mesh<THREE.BufferGeometry, THREE.MeshStandardMaterial>
  age: number
  vel: THREE.Vector3
  spin: number
}

export function serverAmbient(root: THREE.Object3D, scene: THREE.Scene) {
  const sources: THREE.Vector3[] = []
  root.traverse((o) => {
    const p = o.getWorldPosition(new THREE.Vector3())
    if (o.name.startsWith('lamp_')) {
      const l = new THREE.PointLight('#F2F6FF', 16, 12, 1.6)
      l.position.copy(p)
      scene.add(l)
    } else if (o.name.startsWith('smoke_src_')) {
      sources.push(p)
    }
  })

  const geo = new THREE.IcosahedronGeometry(1, 1)
  const puffs: Puff[] = []
  let timer = 0

  function spawn() {
    let p = puffs.find((x) => x.age >= SMOKE_LIFE)
    if (!p) {
      const mat = new THREE.MeshStandardMaterial({ color: '#5E6266', roughness: 1, transparent: true, depthWrite: false, flatShading: true })
      p = { mesh: new THREE.Mesh(geo, mat), age: 0, vel: new THREE.Vector3(), spin: 0 }
      scene.add(p.mesh)
      puffs.push(p)
    }
    const src = sources[Math.floor(Math.random() * sources.length)]
    p.age = 0
    p.mesh.position.copy(src).add(new THREE.Vector3((Math.random() - 0.5) * 0.3, 0, (Math.random() - 0.5) * 0.3))
    p.vel.set((Math.random() - 0.5) * 0.25, 0.45 + Math.random() * 0.35, (Math.random() - 0.5) * 0.25)
    p.spin = (Math.random() - 0.5) * 0.6
    p.mesh.rotation.set(Math.random() * 3, Math.random() * 3, 0)
    p.mesh.visible = true
  }

  return {
    update(dt: number) {
      if (!sources.length) return
      timer -= dt
      while (timer <= 0) {
        spawn()
        timer += SMOKE_EVERY
      }
      for (const p of puffs) {
        if (p.age >= SMOKE_LIFE) {
          p.mesh.visible = false
          continue
        }
        p.age += dt
        const k = p.age / SMOKE_LIFE
        const pos = p.mesh.position
        pos.addScaledVector(p.vel, dt)
        const r = 0.18 + k * 0.9
        if (pos.y > CEILING - r * 0.7) {
          // под потолком дым не поднимается, а расползается
          pos.y = CEILING - r * 0.7
          p.vel.y = 0
          p.vel.x += Math.sign(p.vel.x || 1) * 0.15 * dt
          p.vel.z += Math.sign(p.vel.z || 1) * 0.15 * dt
        }
        p.mesh.rotation.y += p.spin * dt
        p.mesh.scale.set(r * 1.15, r, r * 1.15)
        p.mesh.material.color.lerpColors(SMOKE_DARK, SMOKE_LIGHT, k)
        p.mesh.material.opacity = 0.75 * Math.min(1, p.age * 3) * Math.pow(1 - k, 1.3)
      }
    },
  }
}
