import { Options } from '@popperjs/core'
import { pngxPopperOptions } from './popper-options'

describe('pngxPopperOptions', () => {
  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('should return the config with add padding', () => {
    const config: Partial<Options> = {
      modifiers: [
        {
          name: 'preventOverflow',
          fn: function (arg0) {
            return
          },
        },
      ],
    }

    const result = pngxPopperOptions(config)

    expect(result.modifiers.length).toBe(1)
    expect(result.modifiers[0].name).toBe('preventOverflow')
    expect(result.modifiers[0].options).toEqual({ padding: 10 })
  })

  it('should keep dropdown fallbacks on the same side on mobile', () => {
    jest.spyOn(window, 'matchMedia').mockReturnValue({
      matches: true,
    } as MediaQueryList)
    const config: Partial<Options> = {
      placement: 'bottom-start',
      modifiers: [
        {
          name: 'flip',
          fn: function (arg0) {
            return
          },
          options: {
            fallbackPlacements: ['bottom-end', 'top-start', 'top-end'],
          },
        },
      ],
    }

    const result = pngxPopperOptions(config)

    expect(result.modifiers[0].options.fallbackPlacements).toEqual([
      'bottom-end',
    ])
  })

  it('should retain all dropdown fallbacks outside mobile layouts', () => {
    jest.spyOn(window, 'matchMedia').mockReturnValue({
      matches: false,
    } as MediaQueryList)
    const fallbackPlacements = ['bottom-end', 'top-start', 'top-end']
    const config: Partial<Options> = {
      placement: 'bottom-start',
      modifiers: [
        {
          name: 'flip',
          fn: function (arg0) {
            return
          },
          options: { fallbackPlacements },
        },
      ],
    }

    const result = pngxPopperOptions(config)

    expect(result.modifiers[0].options.fallbackPlacements).toEqual(
      fallbackPlacements
    )
  })
})
