/**
 * DFlip Preview Stage Class
 */

import {
  isMobile,
  isset,
  fixMouseEvent,
  mouseEvents,
  calculateScale,
  getTouches,
  getVectorAvg,
  limitAt,
} from '../utils.js'
import { TWEEN } from '../tween.js'

export class PreviewStage extends MOCKUP.Stage {
  constructor(options) {
    options = options || {}
    const $ = jQuery
    super(options)
    const self = this

    self.options = options
    self.canvas = $(self.renderer.domElement).addClass('df-3dcanvas')
    self.container = options.container
    self.container.append(self.canvas)
    self.type = 'PreviewStage'
    self.mouse = new THREE.Vector2()
    self.raycaster = new THREE.Raycaster()
    self.camera.position.set(0, 20, 600)
    self.camera.lookAt(new THREE.Vector3(0, 0, 0))
    self.spotLight.position.set(-220, 330, 550)
    self.spotLight.castShadow = isMobile ? false : options.webglShadow

    if (self.spotLight.shadow) {
      self.spotLight.shadow.bias = -8e-4
    }

    self.spotLight.intensity = isset(options.spotLightIntensity, 0.22)
    self.ambientLight.color = new THREE.Color(
      isset(options.ambientLightColor, '#fff')
    )
    self.ambientLight.intensity = isset(options.ambientLightIntensity, 0.8)

    const shadowMat = new THREE.ShadowMaterial()
    shadowMat.opacity = isset(options.shadowOpacity, 0.15)
    self.ground.material = shadowMat
    self.ground.position.z = -2

    self.orbitControl.maxAzimuthAngle = 0
    self.orbitControl.minAzimuthAngle = 0
    self.orbitControl.minPolarAngle = Math.PI / 2
    self.orbitControl.maxPolarAngle = 2.2
    self.orbitControl.mouseButtons.ORBIT = THREE.MOUSE.RIGHT
    self.orbitControl.mouseButtons.PAN = -1
    self.orbitControl.maxDistance = 5e3
    self.orbitControl.minDistance = 50
    self.orbitControl.noZoom = true
    self.selectiveRendering = true
    self.orbitControl.zoomSpeed = 5
    self.orbitControl.keyPanSpeed = 0
    self.orbitControl.center.set(0, 0, 0)
    self.orbitControl.update()

    self.swipe_threshold = isMobile ? 15 : 20

    const cssRenderer = (self.cssRenderer = new THREE.CSS3DRenderer())
    $(cssRenderer.domElement)
      .css({ position: 'absolute', top: 0, pointerEvents: 'none' })
      .addClass('df-3dcanvas df-csscanvas')
    self.container[0].appendChild(cssRenderer.domElement)

    const cssScene = (self.cssScene = new THREE.Scene())
    const divLeft = document.createElement('div')
    divLeft.className = 'df-page-content df-page-content-left'
    const divRight = document.createElement('div')
    divRight.className = 'df-page-content df-page-content-right'

    cssScene.divLeft = new THREE.CSS3DObject(divLeft)
    cssScene.divRight = new THREE.CSS3DObject(divRight)
    cssScene.add(cssScene.divLeft)
    cssScene.add(cssScene.divRight)

    self.resizeCallback = () => {
      cssRenderer.setSize(self.canvas.width(), self.canvas.height())
    }

    const requestRender = () => {
      self.renderRequestPending = true
    }

    window.addEventListener(mouseEvents.move, requestRender, false)
    window.addEventListener('keyup', requestRender, false)

    self.dispose = () => {
      self.clearChild()
      self.render()
      window.removeEventListener(mouseEvents.move, requestRender, false)
      if (self.options.scrollWheel == true) {
        self.container[0].removeEventListener('wheel', self.onMouseWheel, false)
      }
      window.removeEventListener('keyup', requestRender, false)
      self.renderer.domElement.removeEventListener(
        'mousemove',
        self.onMouseMove,
        false
      )
      self.renderer.domElement.removeEventListener(
        'touchmove',
        self.onMouseMove,
        false
      )
      self.renderer.domElement.removeEventListener(
        'mousedown',
        self.onMouseDown,
        false
      )
      self.renderer.domElement.removeEventListener(
        'touchstart',
        self.onMouseDown,
        false
      )
      self.renderer.domElement.removeEventListener(
        'mouseup',
        self.onMouseUp,
        false
      )
      self.renderer.domElement.removeEventListener(
        'touchend',
        self.onMouseUp,
        false
      )

      self.canvas.remove()
      if (cssRenderer.domElement.parentNode) {
        cssRenderer.domElement.parentNode.removeChild(cssRenderer.domElement)
      }
      self.cssRenderer = null
      self.renderCallback = null
      if (self.orbitControl) {
        self.orbitControl.dispose()
        self.orbitControl = null
      }
      self.renderer.dispose()
      self.cancelRAF()
    }

    self.renderCallback = () => {
      if (typeof TWEEN !== 'undefined' && TWEEN.getAll().length > 0)
        self.renderRequestPending = true
      if (typeof TWEEN !== 'undefined') TWEEN.update()

      // Enforce pan limits when zoomed
      if (
        self.previewObject &&
        self.previewObject.contentProvider &&
        self.previewObject.contentProvider.zoomScale > 1
      ) {
        const cp = self.previewObject.contentProvider
        const target = self.previewObject.target
        const stageWidth = self.width()
        const zoomWidth = target.zoomWidth
        const maxPanX =
          Math.max(0, (zoomWidth - stageWidth) / 2) + stageWidth * 0.2

        // Limit left panning (negative x is left in Three.js target)
        if (self.orbitControl.target.x < -maxPanX) {
          self.orbitControl.target.x = -maxPanX
          self.orbitControl.update()
        }
        // Limit right panning
        if (self.orbitControl.target.x > maxPanX) {
          self.orbitControl.target.x = maxPanX
          self.orbitControl.update()
        }
      }

      cssRenderer.render(cssScene, self.camera)
    }

    self.onMouseWheel = (e) => {
      let delta = 0
      if (e.deltaY != null) delta = -e.deltaY
      else if (e.wheelDelta != null) delta = e.wheelDelta
      else if (e.detail != null) delta = -e.detail

      if (delta) {
        const zoomScale = self.previewObject.contentProvider.zoomScale
        // Prevent default browser scroll only when zooming
        if ((delta > 0 && zoomScale == 1) || (delta < 0 && zoomScale > 1)) {
          // e.preventDefault();
        }
        self.previewObject.zoom(delta > 0 ? 1 : -1)
      }
      requestRender()
    }

    self.onMouseMove = (e) => {
      self.renderRequestPending = true
      e = fixMouseEvent(e)
      if (self.isMouseDown && e.movementX != 0 && e.movementY != 0) {
        self.isMouseMoving = true
      }
      if (
        e.touches != null &&
        e.touches.length == 2 &&
        self.startTouches != null
      ) {
        self.zoomDirty = true
        const avg = getVectorAvg(getTouches(e, self.container.offset()))
        const scale = calculateScale(self.startTouches, getTouches(e))
        // const n = scale / self.lastScale;
        self.camera.position.z = self.originalZ / scale
        self.lastScale = scale
        self.lastZoomCenter = avg
        e.preventDefault()
        return
      }
      if (
        self.isMouseDown == true &&
        self.previewObject.contentProvider.zoomScale == 1
      ) {
        const deltaX = e.pageX - self.lastPos
        // const deltaTime = performance.now() - self.lastTime;
        if (Math.abs(deltaX) > self.swipe_threshold) {
          if (deltaX < 0) {
            self.target.next()
          } else {
            self.target.prev()
          }
          e.preventDefault()
          self.isMouseDown = false
        }
        self.lastPos = e.pageX
        self.lastTime = performance.now()
      }
    }

    self.onMouseDown = (e) => {
      e = fixMouseEvent(e)
      if (
        e.touches != null &&
        e.touches.length == 2 &&
        self.startTouches == null
      ) {
        self.startTouches = getTouches(e)
        self.lastScale = 1
        self.originalZ = self.camera.position.z * 1
      }
      if (document.activeElement) document.activeElement.blur()
      self.mouseValue = e.pageX + ',' + e.pageY
      self.isMouseMoving = false
      self.isMouseDown = true
      self.lastPos = e.pageX
      self.lastTime = performance.now()
    }

    self.onMouseClick = (e) => {
      self.isMouseDown = false
      if (e.button !== 0) return
      const mouseVal = e.pageX + ',' + e.pageY
      if (!self.isMouseMoving && mouseVal == self.mouseValue) {
        e = e || window.event
        const $e = jQuery.event.fix(e)
        const mouse = self.mouse
        const raycaster = self.raycaster
        mouse.x = ($e.offsetX / self.canvas.innerWidth()) * 2 - 1
        mouse.y = 1 - ($e.offsetY / self.canvas.innerHeight()) * 2
        raycaster.setFromCamera(mouse, self.camera)

        const intersects = raycaster.intersectObjects(
          self.target instanceof MOCKUP.Bundle
            ? self.target.children
            : [self.target],
          true
        )

        if (intersects.length > 0) {
          let obj,
            i = 0
          do {
            obj = intersects[i] ? intersects[i].object : null
            i++
          } while (
            (obj instanceof THREE.BoxHelper ||
              !(obj instanceof MOCKUP.Paper) ||
              obj.isFlipping == true) &&
            i < intersects.length
          )

          if (obj && obj.userData && obj.userData.object == null) {
            if (obj.angles[1] > 90) {
              if (obj.isEdge != true) self.target.next()
            } else {
              if (obj.isEdge != true) self.target.prev()
            }
          }
        }
      }
    }

    self.onMouseUp = (e) => {
      e = fixMouseEvent(e)
      if (e.touches != null && e.touches.length == 0) {
        if (self.zoomDirty == true) {
          self.previewObject.contentProvider.zoomScale = limitAt(
            self.previewObject.contentProvider.zoomScale * self.lastScale,
            1,
            self.previewObject.contentProvider.maxZoom
          )
          self.previewObject.zoomValue =
            self.previewObject.contentProvider.zoomScale * 1
          self.previewObject.resize()
          self.zoomDirty = false
        }
        self.lastScale = null
        self.startTouches = null
      }
      if (e.touches != null && e.touches.length > 1) return
      self.onMouseClick(e)
    }

    self.renderer.domElement.addEventListener(
      'mousemove',
      self.onMouseMove,
      false
    )
    self.renderer.domElement.addEventListener(
      'touchmove',
      self.onMouseMove,
      false
    )
    self.renderer.domElement.addEventListener(
      'mousedown',
      self.onMouseDown,
      false
    )
    self.renderer.domElement.addEventListener(
      'touchstart',
      self.onMouseDown,
      false
    )
    self.renderer.domElement.addEventListener('mouseup', self.onMouseUp, false)
    self.renderer.domElement.addEventListener('touchend', self.onMouseUp, false)

    if (self.options.scrollWheel == true) {
      self.container[0].addEventListener('wheel', self.onMouseWheel, false)
    }

    $(self.renderer.domElement).css({ display: 'block' })
    $(window).trigger('resize')
  }

  width() {
    return this.container.width()
  }

  height() {
    return this.container.height()
  }
}
