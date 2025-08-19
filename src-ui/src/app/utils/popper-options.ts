import { Options } from '@popperjs/core'

export function pngxPopperOptions(config: Partial<Options>): Partial<Options> {
  const preventOverflowModifier = config.modifiers.find(
    (m) => m.name === 'preventOverflow'
  )
  if (preventOverflowModifier) {
    preventOverflowModifier.options = {
      padding: 10,
    }
  }
  return config
}
