/**
 * DFlip TWEEN Library Polyfill
 */

const TWEEN = (function () {
  let _tweens = []
  return {
    getAll: function () {
      return _tweens
    },
    removeAll: function () {
      _tweens = []
    },
    add: function (tween) {
      _tweens.push(tween)
    },
    remove: function (tween) {
      const idx = _tweens.indexOf(tween)
      if (idx !== -1) {
        _tweens.splice(idx, 1)
      }
    },
    update: function (time) {
      if (_tweens.length === 0) return false
      let i = 0
      time = time !== undefined ? time : window.performance.now()
      while (i < _tweens.length) {
        if (_tweens[i].update(time)) {
          i++
        } else {
          _tweens.splice(i, 1)
        }
      }
      return true
    },
  }
})()

TWEEN.Tween = function (object) {
  const _object = object
  let _valuesStart = {}
  let _valuesEnd = {}
  let _valuesStartRepeat = {}
  let _duration = 1000
  let _repeat = 0
  let _yoyo = false
  let _isPlaying = false
  let _reversed = false
  let _delayTime = 0
  let _startTime = null
  let _easingFunction = TWEEN.Easing.Linear.None
  let _interpolationFunction = TWEEN.Interpolation.Linear
  let _chainedTweens = []
  let _onStartCallback = null
  let _onStartCallbackFired = false
  let _onUpdateCallback = null
  let _onCompleteCallback = null
  let _onStopCallback = null

  for (const field in object) {
    _valuesStart[field] = parseFloat(object[field], 10)
  }

  this.to = function (properties, duration) {
    if (duration !== undefined) {
      _duration = duration
    }
    _valuesEnd = properties
    return this
  }

  this.start = function (time) {
    TWEEN.add(this)
    _isPlaying = true
    _onStartCallbackFired = false
    _startTime = time !== undefined ? time : window.performance.now()
    _startTime += _delayTime
    for (const property in _valuesEnd) {
      if (_valuesEnd[property] instanceof Array) {
        if (_valuesEnd[property].length === 0) continue
        _valuesEnd[property] = [_object[property]].concat(_valuesEnd[property])
      }
      if (_valuesStart[property] === undefined) continue
      _valuesStart[property] = _object[property]
      if (_valuesStart[property] instanceof Array === false) {
        _valuesStart[property] *= 1
      }
      _valuesStartRepeat[property] = _valuesStart[property] || 0
    }
    return this
  }

  this.stop = function () {
    if (!_isPlaying) return this
    TWEEN.remove(this)
    _isPlaying = false
    if (_onStopCallback !== null) {
      _onStopCallback.call(_object)
    }
    this.stopChainedTweens()
    return this
  }

  this.stopChainedTweens = function () {
    for (
      let i = 0, numChainedTweens = _chainedTweens.length;
      i < numChainedTweens;
      i++
    ) {
      _chainedTweens[i].stop()
    }
  }

  this.delay = function (amount) {
    _delayTime = amount
    return this
  }

  this.repeat = function (times) {
    _repeat = times
    return this
  }

  this.yoyo = function (yoyo) {
    _yoyo = yoyo
    return this
  }

  this.easing = function (easing) {
    _easingFunction = easing
    return this
  }

  this.interpolation = function (interpolation) {
    _interpolationFunction = interpolation
    return this
  }

  this.chain = function () {
    _chainedTweens = arguments
    return this
  }

  this.onStart = function (callback) {
    _onStartCallback = callback
    return this
  }

  this.onUpdate = function (callback) {
    _onUpdateCallback = callback
    return this
  }

  this.onComplete = function (callback) {
    _onCompleteCallback = callback
    return this
  }

  this.onStop = function (callback) {
    _onStopCallback = callback
    return this
  }

  this.update = function (time) {
    let property
    let elapsed
    let value
    if (time < _startTime) return true
    if (_onStartCallbackFired === false) {
      if (_onStartCallback !== null) {
        _onStartCallback.call(_object)
      }
      _onStartCallbackFired = true
    }
    elapsed = (time - _startTime) / _duration
    elapsed = elapsed > 1 ? 1 : elapsed
    value = _easingFunction(elapsed)
    for (property in _valuesEnd) {
      if (_valuesStart[property] === undefined) continue
      const start = _valuesStart[property] || 0
      let end = _valuesEnd[property]
      if (end instanceof Array) {
        _object[property] = _interpolationFunction(end, value)
      } else {
        if (typeof end === 'string') {
          if (end.startsWith('+') || end.startsWith('-')) {
            end = start + parseFloat(end, 10)
          } else {
            end = parseFloat(end, 10)
          }
        }
        if (typeof end === 'number') {
          _object[property] = start + (end - start) * value
        }
      }
    }
    if (_onUpdateCallback !== null) {
      _onUpdateCallback.call(_object, value)
    }
    if (elapsed === 1) {
      if (_repeat > 0) {
        if (isFinite(_repeat)) {
          _repeat--
        }
        for (property in _valuesStartRepeat) {
          if (typeof _valuesEnd[property] === 'string') {
            _valuesStartRepeat[property] =
              _valuesStartRepeat[property] +
              parseFloat(_valuesEnd[property], 10)
          }
          if (_yoyo) {
            const tmp = _valuesStartRepeat[property]
            _valuesStartRepeat[property] = _valuesEnd[property]
            _valuesEnd[property] = tmp
          }
          _valuesStart[property] = _valuesStartRepeat[property]
        }
        if (_yoyo) {
          _reversed = !_reversed
        }
        _startTime = time + _delayTime
        return true
      } else {
        if (_onCompleteCallback !== null) {
          _onCompleteCallback.call(_object)
        }
        for (
          let i = 0, numChainedTweens = _chainedTweens.length;
          i < numChainedTweens;
          i++
        ) {
          _chainedTweens[i].start(_startTime + _duration)
        }
        return false
      }
    }
    return true
  }
}

TWEEN.Easing = {
  Linear: {
    None: (k) => k,
  },
  Quadratic: {
    In: (k) => k * k,
    Out: (k) => k * (2 - k),
    InOut: (k) => {
      if ((k *= 2) < 1) return 0.5 * k * k
      return -0.5 * (--k * (k - 2) - 1)
    },
  },
  Quartic: {
    In: (k) => k * k * k * k,
    Out: (k) => 1 - --k * k * k * k,
    InOut: (k) => {
      if ((k *= 2) < 1) return 0.5 * k * k * k * k
      return -0.5 * ((k -= 2) * k * k * k - 2)
    },
  },
  Sinusoidal: {
    In: (k) => 1 - Math.cos((k * Math.PI) / 2),
    Out: (k) => Math.sin((k * Math.PI) / 2),
    InOut: (k) => 0.5 * (1 - Math.cos(Math.PI * k)),
  },
  Cubic: {
    In: (k) => k * k * k,
    Out: (k) => --k * k * k + 1,
    InOut: (k) => {
      if ((k *= 2) < 1) return 0.5 * k * k * k
      return 0.5 * ((k -= 2) * k * k + 2)
    },
  },
}

TWEEN.Interpolation = {
  Linear: (v, k) => {
    const m = v.length - 1
    const f = m * k
    const i = Math.floor(f)
    const fn = TWEEN.Interpolation.Utils.Linear
    if (k < 0) return fn(v[0], v[1], f)
    if (k > 1) return fn(v[m], v[m - 1], m - f)
    return fn(v[i], v[i + 1 > m ? m : i + 1], f - i)
  },
  Utils: {
    Linear: (p0, p1, t) => (p1 - p0) * t + p0,
  },
}

window.TWEEN = TWEEN
export default TWEEN
export { TWEEN }
