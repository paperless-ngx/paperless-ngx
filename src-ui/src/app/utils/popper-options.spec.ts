import { popperOptionsReenablePreventOverflow } from './popper-options'
import { Options } from '@popperjs/core'

describe('popperOptionsReenablePreventOverflow', () => {
  it('should return the config without the empty fun preventOverflow, add padding to other', () => {
    const config: Partial<Options> = {
      modifiers: [
        { name: 'preventOverflow', fn: function () {} },
        {
          name: 'preventOverflow',
          fn: function (arg0) {
            return
          },
        },
      ],
    }

    const result = popperOptionsReenablePreventOverflow(config)

    expect(result.modifiers.length).toBe(1)
    expect(result.modifiers[0].name).toBe('preventOverflow')
    expect(result.modifiers[0].options).toEqual({ padding: 10 })
  })
})
