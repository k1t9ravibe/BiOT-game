import * as THREE from 'three'

/**
 * Газоанализатор в руках монтёра — вид «от первого лица» (окно по кнопке Q).
 * Группа крепится к камере окна: камера смотрит по −Z, руки и прибор стоят перед ней снизу.
 * На экране прибора мигает красное «ГАЗ», рядом мигает сигнальный светодиод.
 */

const JACKET = '#2F7FD8' // как куртка у модели монтёра
const STRIPE = '#E8F06A'
const GLOVE = '#2B2F36'
const BODY = '#F2C230'

function screenTexture(on: boolean) {
  const w = 256
  const h = 160
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const g = c.getContext('2d')!
  g.fillStyle = '#0E1216'
  g.fillRect(0, 0, w, h)
  g.fillStyle = on ? '#FF3B30' : '#5A1A17'
  g.font = 'bold 92px Inter, sans-serif'
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText('ГАЗ', w / 2, h / 2 + 4)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

export function gasAnalyzerRig() {
  const group = new THREE.Group()
  const mat = (color: string, rough = 0.7, metal = 0) => new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal, flatShading: true })
  const box = (w: number, h: number, d: number, m: THREE.Material) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m)

  // Прибор: корпус, тёмная рамка экрана, экран, кнопки, датчик сверху, светодиод
  const device = new THREE.Group()
  device.position.set(0, -0.13, -0.42)
  device.rotation.x = -0.45 // верх чуть к себе — экран смотрит в глаза
  device.add(box(0.15, 0.24, 0.055, mat(BODY, 0.5)))
  const bezel = box(0.12, 0.09, 0.006, mat('#1C1F24', 0.6))
  bezel.position.set(0, 0.045, 0.03)
  device.add(bezel)
  const texOn = screenTexture(true)
  const texOff = screenTexture(false)
  const screenMat = new THREE.MeshBasicMaterial({ map: texOn })
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.108, 0.0675), screenMat)
  screen.position.set(0, 0.045, 0.0335)
  device.add(screen)
  for (const bx of [-0.035, 0, 0.035]) {
    const b = box(0.022, 0.016, 0.008, mat('#3A3F45', 0.5))
    b.position.set(bx, -0.04, 0.03)
    device.add(b)
  }
  const sensor = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.018, 0.04, 8), mat('#3A3F45', 0.5))
  sensor.position.set(0.04, 0.14, 0)
  device.add(sensor)
  const ledMat = new THREE.MeshBasicMaterial({ color: '#FF3B30' })
  const led = new THREE.Mesh(new THREE.SphereGeometry(0.009, 10, 8), ledMat)
  led.position.set(-0.05, 0.105, 0.03)
  device.add(led)
  // Шланг пробоотборника уходит вниз — в колодец
  const hose = new THREE.Mesh(new THREE.CylinderGeometry(0.007, 0.007, 0.5, 6), mat('#1C1F24', 0.6))
  hose.position.set(0.02, -0.33, -0.04)
  hose.rotation.x = 0.25
  device.add(hose)
  group.add(device)

  // Руки: рукава куртки со световозвращающей полосой, перчатки держат прибор с боков
  for (const s of [-1, 1]) {
    const glove = box(0.045, 0.11, 0.06, mat(GLOVE, 0.8))
    glove.position.set(s * 0.09, -0.14, -0.41)
    glove.rotation.set(-0.45, 0, s * 0.15)
    group.add(glove)
    const from = new THREE.Vector3(s * 0.1, -0.2, -0.38)
    const to = new THREE.Vector3(s * 0.34, -0.6, -0.06)
    const len = from.distanceTo(to)
    const sleeve = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.075, len, 10), mat(JACKET, 0.8))
    sleeve.position.copy(from).add(to).multiplyScalar(0.5)
    sleeve.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), to.clone().sub(from).normalize())
    group.add(sleeve)
    const cuff = new THREE.Mesh(new THREE.CylinderGeometry(0.053, 0.053, 0.03, 10), mat(STRIPE, 0.5))
    cuff.position.copy(from).lerp(to, 0.22)
    cuff.quaternion.copy(sleeve.quaternion)
    group.add(cuff)
  }

  let lastOn = true
  return {
    group,
    update(t: number) {
      const on = Math.floor(t * 2.5) % 2 === 0 // мигает дважды в секунду
      if (on !== lastOn) {
        lastOn = on
        screenMat.map = on ? texOn : texOff
        screenMat.needsUpdate = true
        ledMat.color.set(on ? '#FF3B30' : '#4A1512')
      }
    },
  }
}
