/**
 * DFlip Book Paper Class
 */

import { DIRECTION } from '../constants.js'
import { isBookletMode } from '../utils.js'
import { TWEEN } from '../tween.js'

export class BookPaper extends MOCKUP.FlexBoxPaper {
  constructor(options, mockup) {
    options = options || {}
    options.folds = 1
    super(options, mockup)
    this.angle = 0
    this.isFlipping = false
    this.material.materials[5].transparent = true
    this.material.materials[4].transparent = true
    this.type = 'BookPaper'
  }

  tween(startAngle, endAngle) {
    const self = this
    const EPSILON = 1e-5
    self.originalStiff = self.stiffness
    const targetStiffness = self.newStiffness
    const isBooklet = isBookletMode(self.parent)
    const deltaAngle = endAngle - startAngle
    const isPast90 = startAngle > 90
    const isRTL = self.parent.direction == DIRECTION.RTL

    self.init = {
      angle: startAngle,
      angle2: startAngle < 90 ? 0 : 180,
      stiff: self.originalStiff,
      index: (isPast90 && !isRTL) || (!isPast90 && isRTL) ? 1 : 0,
    }
    self.first = {
      angle: startAngle + deltaAngle / 4,
      angle2: startAngle < 90 ? 90 : 90,
      stiff: self.originalStiff,
      index: (isPast90 && !isRTL) || (!isPast90 && isRTL) ? 1 : 0.25,
    }
    self.mid = {
      angle: startAngle + (deltaAngle * 2) / 4,
      angle2: startAngle < 90 ? 135 : 45,
      stiff: self.newStiffness,
      index: (isPast90 && !isRTL) || (!isPast90 && isRTL) ? 0.5 : 0.5,
    }
    self.mid2 = {
      angle: startAngle + (deltaAngle * 3) / 4,
      angle2: startAngle < 90 ? 180 : 0,
      stiff: self.newStiffness,
      index: (isPast90 && !isRTL) || (!isPast90 && isRTL) ? 0.25 : 1,
    }
    self.end = {
      angle: endAngle,
      angle2: startAngle < 90 ? 180 : 0,
      stiff: self.newStiffness,
      index: (isPast90 && !isRTL) || (!isPast90 && isRTL) ? 0 : 1,
    }
    self.isFlipping = true

    const updateTween = (state) => {
      self.angles[1] = state.angle
      self.angles[4] = self.isHard ? state.angle : state.angle2
      if (self.isHard == true) {
        self.stiffness = 0
      } else {
        self.stiffness =
          (state.stiff / (targetStiffness + EPSILON)) *
          (self.newStiffness + EPSILON)
        self.stiffness = isNaN(self.stiffness) ? 0 : state.stiff
      }
      if (isBooklet) {
        self.material.materials[5].opacity =
          self.material.materials[4].opacity = state.index
        self.castShadow =
          (isPast90 && !isRTL) || (!isPast90 && isRTL)
            ? state.index > 0.5
            : state.index > 0.5
      }
      self.updateAngle(true)
    }

    if (isBooklet && ((!isPast90 && !isRTL) || (isPast90 && isRTL))) {
      self.material.materials[5].opacity =
        self.material.materials[4].opacity = 0
      self.castShadow = false
    }

    self.currentTween = new TWEEN.Tween(self.init)
      .to(
        {
          angle: [
            self.first.angle,
            self.mid.angle,
            self.mid2.angle,
            self.end.angle,
          ],
          angle2: [
            self.first.angle2,
            self.mid.angle2,
            self.mid2.angle2,
            self.end.angle2,
          ],
          stiff: [
            self.first.stiff,
            self.mid.stiff,
            self.mid2.stiff,
            self.end.stiff,
          ],
          index: [
            self.first.index,
            self.mid.index,
            self.mid2.index,
            self.end.index,
          ],
        },
        self.parent.duration
      )
      .onUpdate(function () {
        updateTween(this)
      })
      .easing(TWEEN.Easing.Cubic.Out)
      .onComplete(() => {
        self.stiffness = self.newStiffness
        self.updateAngle()
        self.material.materials[5].opacity =
          self.material.materials[4].opacity = 1
        self.castShadow = true
        self.isFlipping = false
        if (self.parent && self.parent.refresh) self.parent.refresh()
      })
      .start()
  }
}
