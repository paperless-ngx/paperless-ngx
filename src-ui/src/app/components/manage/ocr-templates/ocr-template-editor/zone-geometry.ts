import { OcrTemplateZone } from 'src/app/data/ocr-template'

export interface DrawingRect {
  startX: number
  startY: number
  endX: number
  endY: number
}

export interface Dimensions {
  width: number
  height: number
}

export interface Point {
  x: number
  y: number
}

export interface DisplayRect {
  x: number
  y: number
  w: number
  h: number
}

export interface MoveStart {
  mouseX: number
  mouseY: number
  zoneX: number
  zoneY: number
}

export type ResizeHandle = 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const HANDLE_SIZE = 8
export const MIN_ZONE_SIZE = 10

export function getZonePage(
  zone: OcrTemplateZone,
  previewPage: number,
  previewPageCount: number | null
): number {
  const page = zone.page ?? 1
  if (page === -1) return previewPageCount ?? previewPage + 1
  return page >= 1 ? page : 1
}

export function isZoneOnPage(
  zone: OcrTemplateZone,
  previewPage: number,
  previewPageCount: number | null
): boolean {
  return getZonePage(zone, previewPage, previewPageCount) === previewPage + 1
}

export function getZoneSourceSize(
  zone: OcrTemplateZone,
  imageSize: Dimensions
): Dimensions {
  return {
    width: zone.zone_source_width || imageSize.width,
    height: zone.zone_source_height || imageSize.height,
  }
}

export function getZoneDisplayRect(
  zone: OcrTemplateZone,
  canvasSize: Dimensions,
  imageSize: Dimensions
): DisplayRect {
  const sourceSize = getZoneSourceSize(zone, imageSize)
  const scaleX = canvasSize.width / sourceSize.width
  const scaleY = canvasSize.height / sourceSize.height

  return {
    x: zone.x * scaleX,
    y: zone.y * scaleY,
    w: zone.width * scaleX,
    h: zone.height * scaleY,
  }
}

export function findHandleAt(
  point: Point,
  rect: DisplayRect,
  handleSize = HANDLE_SIZE
): ResizeHandle | null {
  const handles: [ResizeHandle, number, number][] = [
    ['nw', rect.x, rect.y],
    ['n', rect.x + rect.w / 2, rect.y],
    ['ne', rect.x + rect.w, rect.y],
    ['w', rect.x, rect.y + rect.h / 2],
    ['e', rect.x + rect.w, rect.y + rect.h / 2],
    ['sw', rect.x, rect.y + rect.h],
    ['s', rect.x + rect.w / 2, rect.y + rect.h],
    ['se', rect.x + rect.w, rect.y + rect.h],
  ]

  return (
    handles.find(
      ([, x, y]) =>
        Math.abs(point.x - x) <= handleSize &&
        Math.abs(point.y - y) <= handleSize
    )?.[0] ?? null
  )
}

export function findZoneAt(
  point: Point,
  zones: OcrTemplateZone[],
  previewPage: number,
  previewPageCount: number | null,
  canvasSize: Dimensions,
  imageSize: Dimensions
): number | null {
  for (let i = zones.length - 1; i >= 0; i--) {
    const zone = zones[i]
    if (!isZoneOnPage(zone, previewPage, previewPageCount)) continue
    const rect = getZoneDisplayRect(zone, canvasSize, imageSize)

    if (
      point.x >= rect.x &&
      point.x <= rect.x + rect.w &&
      point.y >= rect.y &&
      point.y <= rect.y + rect.h
    ) {
      return i
    }
  }

  return null
}

export function moveZone(
  zone: OcrTemplateZone,
  point: Point,
  moveStart: MoveStart,
  canvasSize: Dimensions,
  imageSize: Dimensions
) {
  const sourceSize = getZoneSourceSize(zone, imageSize)
  const scaleX = sourceSize.width / canvasSize.width
  const scaleY = sourceSize.height / canvasSize.height
  const dx = Math.round((point.x - moveStart.mouseX) * scaleX)
  const dy = Math.round((point.y - moveStart.mouseY) * scaleY)

  zone.x = clamp(moveStart.zoneX + dx, 0, sourceSize.width - zone.width)
  zone.y = clamp(moveStart.zoneY + dy, 0, sourceSize.height - zone.height)
}

export function resizeZone(
  zone: OcrTemplateZone,
  handle: ResizeHandle,
  point: Point,
  canvasSize: Dimensions,
  imageSize: Dimensions
) {
  const sourceSize = getZoneSourceSize(zone, imageSize)
  const scaleX = sourceSize.width / canvasSize.width
  const scaleY = sourceSize.height / canvasSize.height
  const imageX = clamp(Math.round(point.x * scaleX), 0, sourceSize.width)
  const imageY = clamp(Math.round(point.y * scaleY), 0, sourceSize.height)

  if (handle.includes('w')) {
    const right = Math.min(zone.x + zone.width, sourceSize.width)
    zone.x = clamp(imageX, 0, right - MIN_ZONE_SIZE)
    zone.width = right - zone.x
  }
  if (handle.includes('e')) {
    zone.width = Math.max(MIN_ZONE_SIZE, imageX - zone.x)
  }
  if (handle.includes('n')) {
    const bottom = Math.min(zone.y + zone.height, sourceSize.height)
    zone.y = clamp(imageY, 0, bottom - MIN_ZONE_SIZE)
    zone.height = bottom - zone.y
  }
  if (handle.includes('s')) {
    zone.height = Math.max(MIN_ZONE_SIZE, imageY - zone.y)
  }
}

export function sourceRectFromDrawing(
  rect: DrawingRect,
  canvasSize: Dimensions,
  imageSize: Dimensions
): DisplayRect {
  const scaleX = imageSize.width / canvasSize.width
  const scaleY = imageSize.height / canvasSize.height

  return {
    x: Math.round(Math.min(rect.startX, rect.endX) * scaleX),
    y: Math.round(Math.min(rect.startY, rect.endY) * scaleY),
    w: Math.round(Math.abs(rect.endX - rect.startX) * scaleX),
    h: Math.round(Math.abs(rect.endY - rect.startY) * scaleY),
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(value, max))
}
