import { Options } from '@popperjs/core'

export function popperOptionsReenablePreventOverflow(
  config: Partial<Options>
): Partial<Options> {
  const preventOverflowModifier = config.modifiers?.find(
    (m) => m.name === 'preventOverflow' && m.fn?.length === 0
  )
  if (preventOverflowModifier) {
    config.modifiers.splice(
      config.modifiers.indexOf(preventOverflowModifier),
      1
    )
  }
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
