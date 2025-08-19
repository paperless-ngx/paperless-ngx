import { Options } from '@popperjs/core'
import { pngxPopperOptions } from './popper-options'

describe('popperOptionsReenablePreventOverflow', () => {
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
})
