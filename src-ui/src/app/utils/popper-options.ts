import { Options } from '@popperjs/core'

export function popperOptionsReenablePreventOverflow(
  config: Partial<Options>
): Partial<Options> {
  config.modifiers = config.modifiers?.filter(
    (m) => !(m.name === 'preventOverflow' && m.fn?.length === 0)
  )
  const ogPreventOverflowModifier = config.modifiers.find(
    (m) => m.name === 'preventOverflow'
  )
  if (ogPreventOverflowModifier) {
    ogPreventOverflowModifier.options = {
      padding: 10,
    }
  }
  return config
}
