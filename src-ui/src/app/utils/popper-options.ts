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

  const flipModifier = config.modifiers.find((m) => m.name === 'flip')
  const placementSide = config.placement?.split('-')[0]
  if (
    flipModifier &&
    placementSide &&
    window.matchMedia('(max-width: 575.98px)').matches
  ) {
    flipModifier.options = {
      ...flipModifier.options,
      fallbackPlacements: (
        flipModifier.options?.fallbackPlacements ?? []
      ).filter((placement) => placement.startsWith(placementSide)),
    }
  }

  return config
}
