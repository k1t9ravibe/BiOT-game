import * as THREE from 'three'
import type { WalkSky } from '../walk/engine'

/**
 * Локация 4 «Серверная» (blender/build_server.py): помещение с окном. Днём в окно светит солнце,
 * рассеянный свет мягче уличного, потолочные светильники (пустышки lamp_<n>) горят холодным белым.
 */

export const ROOM_SKY: WalkSky = {
  background: '#BFDDF2',
  fog: '#CFE6F5',
  hemi: ['#FFFFFF', '#9AA1AA', 0.9],
  sun: ['#FFF1D6', 2.6, [4, 9, -14]], // со стороны окна (стена +Y в Blender — −z в игре)
}

export function serverAmbient(root: THREE.Object3D, scene: THREE.Scene) {
  root.traverse((o) => {
    if (!o.name.startsWith('lamp_')) return
    const l = new THREE.PointLight('#F2F6FF', 6, 9, 2)
    l.position.copy(o.getWorldPosition(new THREE.Vector3()))
    scene.add(l)
  })
  return { update() {} }
}
