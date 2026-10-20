import { OcrTemplateZone } from 'src/app/data/ocr-template'
import {
  findHandleAt,
  findZoneAt,
  getResizeHandles,
  getZoneDisplayRect,
  getZonePage,
  isZoneOnPage,
  moveZone,
  resizeZone,
} from './zone-geometry'

function zone(overrides: Partial<OcrTemplateZone> = {}): OcrTemplateZone {
  return {
    name: 'Zone',
    target: 'custom_field',
    custom_field: 1,
    x: 100,
    y: 200,
    width: 300,
    height: 400,
    page: 1,
    ocr_language: 'eng',
    transform: 'strip',
    validation_regex: '',
    order: 0,
    ...overrides,
  }
}

describe('OCR template editor geometry', () => {
  it('normalizes zone pages', () => {
    expect(getZonePage(zone({ page: 2 }), 0, 5)).toBe(2)
    expect(getZonePage(zone({ page: -1 }), 0, 5)).toBe(5)
    expect(getZonePage(zone({ page: -1 }), 2, null)).toBe(3)
    expect(getZonePage(zone({ page: 0 }), 0, 5)).toBe(1)
    expect(getZonePage(zone({ page: undefined }), 0, 5)).toBe(1)
  })

  it('checks whether a zone is on the current preview page', () => {
    expect(isZoneOnPage(zone({ page: 2 }), 1, 5)).toBe(true)
    expect(isZoneOnPage(zone({ page: 2 }), 0, 5)).toBe(false)
    expect(isZoneOnPage(zone({ page: -1 }), 4, 5)).toBe(true)
  })

  it('uses natural image coordinates when source dimensions are unset', () => {
    expect(
      getZoneDisplayRect(zone({ x: 100, y: 200, width: 300, height: 400 }), {
        width: 1000,
        height: 2000,
      })
    ).toEqual({ x: 100, y: 200, w: 300, h: 400 })
  })

  it('uses per-zone source dimensions when present', () => {
    expect(
      getZoneDisplayRect(
        zone({
          x: 100,
          y: 100,
          width: 100,
          height: 100,
          zone_source_width: 1000,
          zone_source_height: 1000,
        }),
        { width: 500, height: 750 }
      )
    ).toEqual({ x: 50, y: 75, w: 50, h: 75 })
  })

  it('finds zones from topmost to bottommost on the current page', () => {
    const zones = [
      zone({ name: 'first', x: 0, y: 0, width: 100, height: 100, page: 1 }),
      zone({ name: 'second', x: 0, y: 0, width: 50, height: 50, page: 1 }),
      zone({ name: 'third', x: 0, y: 0, width: 50, height: 50, page: 2 }),
    ]

    expect(
      findZoneAt({ x: 25, y: 25 }, zones, 0, 2, { width: 100, height: 100 })
    ).toBe(1)
  })

  it('finds resize handles around a display rect', () => {
    const rect = { x: 10, y: 20, w: 100, h: 200 }

    expect(findHandleAt({ x: 10, y: 20 }, rect)).toBe('nw')
    expect(findHandleAt({ x: 110, y: 220 }, rect)).toBe('se')
    expect(findHandleAt({ x: 60, y: 20 }, rect)).toBe('n')
    expect(findHandleAt({ x: 90, y: 160 }, rect)).toBeNull()
    expect(findHandleAt({ x: 19, y: 20 }, rect, 8)).toBeNull()
    expect(findHandleAt({ x: 19, y: 20 }, rect, 10)).toBe('nw')
  })

  it('uses the rendered handle positions for hit testing', () => {
    const rect = { x: 10, y: 20, w: 100, h: 200 }
    const handles = getResizeHandles(rect)

    expect(handles).toEqual([
      { handle: 'nw', x: 10, y: 20 },
      { handle: 'n', x: 60, y: 20 },
      { handle: 'ne', x: 110, y: 20 },
      { handle: 'w', x: 10, y: 120 },
      { handle: 'e', x: 110, y: 120 },
      { handle: 'sw', x: 10, y: 220 },
      { handle: 's', x: 60, y: 220 },
      { handle: 'se', x: 110, y: 220 },
    ])
    for (const marker of handles) {
      expect(findHandleAt(marker, rect)).toBe(marker.handle)
    }
  })

  it('moves zones without leaving source image bounds', () => {
    const z = zone({ x: 50, y: 50, width: 100, height: 100 })

    moveZone(
      z,
      { x: 500, y: 500 },
      { mouseX: 50, mouseY: 50, zoneX: 50, zoneY: 50 },
      { width: 500, height: 500 }
    )

    expect(z.x).toBe(400)
    expect(z.y).toBe(400)
  })

  it('resizes zones without leaving source image bounds', () => {
    const z = zone({
      x: 50,
      y: 50,
      width: 100,
      height: 100,
      zone_source_width: 200,
      zone_source_height: 200,
    })

    resizeZone(z, 'se', { x: 500, y: 500 }, { width: 500, height: 500 })

    expect(z.width).toBe(150)
    expect(z.height).toBe(150)
  })

  it('moves zones in their original source coordinates on a different-size preview', () => {
    const z = zone({
      x: 50,
      y: 50,
      width: 100,
      height: 100,
      zone_source_width: 1000,
      zone_source_height: 2000,
    })

    moveZone(
      z,
      { x: 75, y: 75 },
      { mouseX: 25, mouseY: 25, zoneX: 50, zoneY: 50 },
      { width: 500, height: 500 }
    )

    expect(z.x).toBe(150)
    expect(z.y).toBe(250)
  })
})
