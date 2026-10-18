import * as THREE from 'three'
import { cityAmbient } from '../city/ambient'
import type { WalkSky } from '../walk/engine'

/**
 * Локация 3 «Вечерний город» (blender/build_evening.py): сумерки, горят фонари, оборванный провод искрит.
 * Прохожие — как в городе (cityAmbient); сверх того по пустышкам из сцены:
 *   glow_<n>  — пятно тёплого света фонаря на земле
 *   lamp_<n>  — точечный свет фонаря (только у маршрута игрока — каждый источник дорог для видеокарты)
 *   spark_src — конец оборванного провода: искры вспышками и голубой свет дуги
 */

export const EVENING_SKY: WalkSky = {
  background: '#2E3A63',
  fog: '#3A4470',
  hemi: ['#7487C2', '#2A2F3A', 0.75],
  sun: ['#FF9A5C', 0.7, [-30, 9, 6]], // низкое закатное солнце с запада
}

const GLOW_R = 4.5
const SPARK_N = 60
const SPARK_LIFE = 0.7
const GRAVITY = 9.8

/** Круг с мягким краем — пятно света на земле */
function glowTexture() {
  const c = document.createElement('canvas')
  c.width = c.height = 128
  const g = c.getContext('2d')!
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64)
  grad.addColorStop(0, 'rgba(255,214,150,0.55)')
  grad.addColorStop(0.5, 'rgba(255,190,120,0.22)')
  grad.addColorStop(1, 'rgba(255,170,90,0)')
  g.fillStyle = grad
  g.fillRect(0, 0, 128, 128)
  return new THREE.CanvasTexture(c)
}

export function eveningAmbient(root: THREE.Object3D, scene: THREE.Scene) {
  const city = cityAmbient(root, scene)
  const empties = (prefix: string) => {
    const out: THREE.Vector3[] = []
    root.traverse((o) => {
      if (o.name.startsWith(prefix)) out.push(o.getWorldPosition(new THREE.Vector3()))
    })
    return out
  }

  // Пятна света под фонарями: прозрачные круги поверх асфальта и плитки
  const glowMat = new THREE.MeshBasicMaterial({
    map: glowTexture(),
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    fog: true,
  })
  const glowGeo = new THREE.CircleGeometry(GLOW_R, 32).rotateX(-Math.PI / 2)
  for (const p of empties('glow_')) {
    const m = new THREE.Mesh(glowGeo, glowMat)
    m.position.copy(p)
    m.renderOrder = 1
    scene.add(m)
  }
  for (const p of empties('lamp_')) {
    const l = new THREE.PointLight('#FFC98A', 40, 16, 2)
    l.position.copy(p)
    scene.add(l)
  }

  // Искры: точки летят из конца провода и падают; вспышки идут сериями
  const src = empties('spark_src')[0]
  const sparks = { pos: new Float32Array(SPARK_N * 3), vel: new Float32Array(SPARK_N * 3), age: new Float32Array(SPARK_N) }
  sparks.age.fill(SPARK_LIFE)
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(sparks.pos, 3))
  const points = new THREE.Points(
    geo,
    new THREE.PointsMaterial({ color: '#FFF2B0', size: 0.07, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }),
  )
  points.frustumCulled = false
  const arc = new THREE.PointLight('#9FD0FF', 0, 7, 2)
  if (src) {
    scene.add(points)
    arc.position.copy(src).add(new THREE.Vector3(0, 0.3, 0))
    scene.add(arc)
  }
  let burst = 0 // сколько ещё секунд идёт вспышка
  let pause = 0.5
  let next = 0

  function emit(n: number) {
    for (let i = 0; i < SPARK_N && n > 0; i++) {
      if (sparks.age[i] < SPARK_LIFE) continue
      sparks.age[i] = Math.random() * 0.2
      sparks.pos.set([src!.x, src!.y, src!.z], i * 3)
      const a = Math.random() * Math.PI * 2
      const h = 0.6 + Math.random() * 1.6
      sparks.vel.set([Math.cos(a) * h, 1.2 + Math.random() * 2.2, Math.sin(a) * h], i * 3)
      n--
    }
  }

  function updateSparks(dt: number) {
    if (!src) return
    if (burst > 0) {
      burst -= dt
      next -= dt
      if (next <= 0) {
        emit(6 + Math.floor(Math.random() * 8))
        next = 0.04 + Math.random() * 0.08
      }
      arc.intensity = 6 + Math.random() * 14
      if (burst <= 0) pause = 0.6 + Math.random() * 2.2
    } else {
      arc.intensity = 0
      pause -= dt
      if (pause <= 0) burst = 0.15 + Math.random() * 0.5
    }
    for (let i = 0; i < SPARK_N; i++) {
      if (sparks.age[i] >= SPARK_LIFE) {
        sparks.pos[i * 3 + 1] = -100 // прячем под землю
        continue
      }
      sparks.age[i] += dt
      sparks.vel[i * 3 + 1] -= GRAVITY * dt
      for (let k = 0; k < 3; k++) sparks.pos[i * 3 + k] += sparks.vel[i * 3 + k] * dt
      if (sparks.pos[i * 3 + 1] < 0.02) {
        // отскок от асфальта с потерей скорости
        sparks.pos[i * 3 + 1] = 0.02
        sparks.vel[i * 3 + 1] *= -0.3
        sparks.vel[i * 3] *= 0.5
        sparks.vel[i * 3 + 2] *= 0.5
      }
    }
    geo.attributes.position.needsUpdate = true
  }

  return {
    update(dt: number, t: number) {
      city.update(dt, t)
      updateSparks(dt)
    },
  }
}
