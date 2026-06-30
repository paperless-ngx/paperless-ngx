import { CommonModule } from '@angular/common'
import {
  Component,
  ElementRef,
  HostListener,
  inject,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import {
  NgbNavModule,
  NgbPopoverModule,
  NgbTypeaheadModule,
  NgbTypeaheadSelectItemEvent,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import {
  catchError,
  debounceTime,
  distinctUntilChanged,
  map,
  Observable,
  of,
  Subject,
  switchMap,
  takeUntil,
} from 'rxjs'
import { SelectComponent } from 'src/app/components/common/input/select/select.component'
import { SwitchComponent } from 'src/app/components/common/input/switch/switch.component'
import { TextComponent } from 'src/app/components/common/input/text/text.component'
import { PageHeaderComponent } from 'src/app/components/common/page-header/page-header.component'
import { CustomField, CustomFieldDataType } from 'src/app/data/custom-field'
import { Document } from 'src/app/data/document'
import { DocumentType } from 'src/app/data/document-type'
import {
  DATE_FORMAT_OPTIONS,
  DEFAULT_OCR_ZONE_LANGUAGE,
  DEFAULT_OCR_ZONE_TARGET,
  DEFAULT_OCR_ZONE_TRANSFORM,
  isOcrBuiltinTarget,
  OCR_BUILTIN_TARGETS,
  OCR_LANGUAGE_OPTIONS,
  OCR_ZONE_TARGET,
  OCR_ZONE_TRANSFORM,
  OcrBuiltinTarget,
  OcrTemplate,
  OcrTemplateZone,
  OcrZoneTestResult,
  TRANSFORM_OPTIONS,
  ZoneTestRequest,
} from 'src/app/data/ocr-template'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { ToastService } from 'src/app/services/toast.service'
import { OcrTemplateEditorZoneListComponent } from './ocr-template-editor-zone-list/ocr-template-editor-zone-list.component'
import {
  DisplayRect,
  DrawingRect,
  findHandleAt,
  findZoneAt,
  getZoneDisplayRect,
  getZonePage,
  HANDLE_SIZE,
  isZoneOnPage,
  MoveStart,
  moveZone,
  Point,
  ResizeHandle,
  resizeZone,
} from './zone-geometry'

type ActiveTab = 'settings' | 'zones' | 'zone'
type ZoneFieldSelection = OcrBuiltinTarget | number | null
type OverlayInteraction =
  | { kind: 'idle' }
  | { kind: 'drawing'; rect: DrawingRect }
  | { kind: 'moving'; zoneIndex: number; start: MoveStart }
  | { kind: 'resizing'; zoneIndex: number; handle: ResizeHandle }
interface ResizeHandleMarker extends Point {
  handle: ResizeHandle
}

const CUSTOM_DATE_FORMAT_CHOICE = 'custom'
const MIN_DRAWN_ZONE_SIZE = 10
const NO_OVERLAY_INTERACTION: OverlayInteraction = { kind: 'idle' }
const ZONE_COLORS = [
  '#4f8ff7',
  '#ff6b6b',
  '#51cf66',
  '#ffd43b',
  '#cc5de8',
  '#ff922b',
  '#20c997',
  '#e599f7',
]
const RESIZE_CURSOR: Record<ResizeHandle, string> = {
  nw: 'nw-resize',
  ne: 'ne-resize',
  sw: 'sw-resize',
  se: 'se-resize',
  n: 'n-resize',
  s: 's-resize',
  w: 'w-resize',
  e: 'e-resize',
}

@Component({
  selector: 'pngx-ocr-template-editor',
  standalone: true,
  imports: [
    PageHeaderComponent,
    TextComponent,
    SelectComponent,
    SwitchComponent,
    CommonModule,
    FormsModule,
    RouterModule,
    NgbNavModule,
    NgbPopoverModule,
    NgbTypeaheadModule,
    NgSelectModule,
    NgxBootstrapIconsModule,
    OcrTemplateEditorZoneListComponent,
  ],
  templateUrl: './ocr-template-editor.component.html',
  styleUrls: ['./ocr-template-editor.component.scss'],
})
export class OcrTemplateEditorComponent implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly templateService = inject(OcrTemplateService)
  private readonly customFieldsService = inject(CustomFieldsService)
  private readonly documentTypeService = inject(DocumentTypeService)
  private readonly correspondentService = inject(CorrespondentService)
  private readonly documentService = inject(DocumentService)
  private readonly toastService = inject(ToastService)
  private readonly destroy$ = new Subject<void>()
  private readonly customDateFormatZones = new WeakSet<OcrTemplateZone>()

  @ViewChild('zoneOverlay') overlayRef: ElementRef<SVGSVGElement>
  @ViewChild('pageImage') imageRef: ElementRef<HTMLImageElement>

  template: OcrTemplate = {
    id: null,
    name: '',
    document_type: null,
    sample_document: null,
    source_width: 0,
    source_height: 0,
    enabled: true,
    combine_formats: {},
    zones: [],
  }

  customFields: CustomField[] = []
  documentTypes: DocumentType[] = []
  transformOptions = TRANSFORM_OPTIONS
  builtinTargets = OCR_BUILTIN_TARGETS
  dateFormatOptions = DATE_FORMAT_OPTIONS
  ocrLanguageOptions = OCR_LANGUAGE_OPTIONS
  dateTransform = OCR_ZONE_TRANSFORM.Date
  customDateFormatChoice = CUSTOM_DATE_FORMAT_CHOICE
  isNew = true
  saving = false

  previewDocId: number | null = null
  previewPage = 0
  previewPageCount: number | null = null
  private pageCountForDoc: number | null = null
  pageImageUrl: string | null = null
  imageLoaded = false
  zoom = 1
  previewDocModel: Document | string = ''
  private correspondentNames = new Map<number, string>()

  public get previewPageDisplay(): number {
    return this.previewPage + 1
  }

  public set previewPageDisplay(value: number) {
    this.goToPage(value - 1)
  }

  activeTab: ActiveTab = 'settings'

  selectedZoneIndex: number | null = null
  private overlayInteraction: OverlayInteraction = NO_OVERLAY_INTERACTION
  overlayCursor = 'crosshair'

  zoneTestResult: OcrZoneTestResult | null = null
  zoneTesting = false

  showQuickCreate = false
  quickCreateName = ''
  quickCreateType = CustomFieldDataType.String
  quickCreateForZoneIndex: number | null = null
  quickCreateTypes = [
    { id: CustomFieldDataType.String, name: $localize`String` },
    { id: CustomFieldDataType.Integer, name: $localize`Integer` },
    { id: CustomFieldDataType.Float, name: $localize`Float` },
    { id: CustomFieldDataType.Date, name: $localize`Date` },
    { id: CustomFieldDataType.Monetary, name: $localize`Monetary` },
    { id: CustomFieldDataType.Boolean, name: $localize`Boolean` },
    { id: CustomFieldDataType.Url, name: $localize`URL` },
    { id: CustomFieldDataType.LongText, name: $localize`Long Text` },
  ]

  get selectedZone(): OcrTemplateZone | null {
    return this.selectedZoneIndex !== null
      ? (this.template.zones[this.selectedZoneIndex] ?? null)
      : null
  }

  get pageTitle(): string {
    return this.isNew
      ? $localize`New OCR Template`
      : $localize`Edit OCR Template`
  }

  ngOnInit() {
    this.customFieldsService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.customFields = r.results))

    this.documentTypeService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.documentTypes = r.results))

    this.correspondentService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => {
        this.correspondentNames = new Map(r.results.map((c) => [c.id, c.name]))
      })

    const id = this.route.snapshot.paramMap.get('id')
    if (id && id !== 'new') {
      this.isNew = false
      this.templateService
        .get(parseInt(id))
        .pipe(takeUntil(this.destroy$))
        .subscribe((t) => {
          this.template = t
          this.template.combine_formats ??= {}
          if (t.sample_document) {
            this.previewDocId = t.sample_document
            this.loadPreview()
          }
        })
    } else {
      const qp = this.route.snapshot.queryParams
      if (qp['document_type']) {
        this.template.document_type = parseInt(qp['document_type'])
      }
      if (qp['sample_document']) {
        const docId = parseInt(qp['sample_document'])
        this.template.sample_document = docId
        this.previewDocId = docId
        this.loadPreview()
      }
    }
  }

  searchDocuments = (text$: Observable<string>): Observable<Document[]> =>
    text$.pipe(
      debounceTime(250),
      distinctUntilChanged(),
      switchMap((term) => {
        if (!term || term.trim().length < 2) return of([])
        const params: { title__icontains: string; document_type__id?: number } =
          { title__icontains: term.trim() }
        if (this.template.document_type) {
          params['document_type__id'] = this.template.document_type
        }
        return this.documentService.list(1, 10, 'created', true, params).pipe(
          map((r) => r.results),
          catchError(() => of([]))
        )
      })
    )

  documentFormatter = (doc: Document | string): string => {
    if (typeof doc === 'string') return doc
    const corr = doc.correspondent
      ? this.correspondentNames.get(doc.correspondent)
      : null
    return corr
      ? `#${doc.id} ${doc.title} (${corr})`
      : `#${doc.id} ${doc.title}`
  }

  onPreviewDocSelected(event: NgbTypeaheadSelectItemEvent<Document>) {
    event.preventDefault()
    const doc: Document = event.item
    this.previewDocModel = doc
    this.previewDocId = doc.id
    if (!this.template.document_type && doc.document_type) {
      this.template.document_type = doc.document_type
    }
    this.previewPage = 0
    this.loadPreview()
  }

  clearPreviewDoc() {
    this.previewDocModel = ''
    this.previewDocId = null
    this.previewPageCount = null
    this.pageCountForDoc = null
    this.previewPage = 0
    this.pageImageUrl = null
    this.imageLoaded = false
  }

  loadPreview() {
    if (!this.previewDocId) return
    if (this.pageCountForDoc !== this.previewDocId) {
      this.pageCountForDoc = this.previewDocId
      this.previewPageCount = null
      this.documentService
        .get(this.previewDocId)
        .pipe(takeUntil(this.destroy$))
        .subscribe({
          next: (doc) => {
            this.previewPageCount = doc?.page_count ?? null
            if (doc && !this.previewDocModel) this.previewDocModel = doc
          },
          error: () => (this.previewPageCount = null),
        })
    }
    this.pageImageUrl = this.templateService.getPageImageUrl(
      this.previewDocId,
      this.previewPage
    )
    this.imageLoaded = false
  }

  goToPage(page: number) {
    if (!Number.isFinite(page)) return
    const max = this.previewPageCount ? this.previewPageCount - 1 : page
    const clamped = Math.max(0, Math.min(page, max))
    if (clamped === this.previewPage) return
    this.previewPage = clamped
    this.loadPreview()
  }

  prevPage() {
    this.goToPage(this.previewPage - 1)
  }

  nextPage() {
    this.goToPage(this.previewPage + 1)
  }

  zoomIn() {
    this.zoom = Math.min(4, Math.round((this.zoom + 0.25) * 100) / 100)
  }

  zoomOut() {
    this.zoom = Math.max(0.5, Math.round((this.zoom - 0.25) * 100) / 100)
  }

  resetZoom() {
    this.zoom = 1
  }

  zonePage(zone: OcrTemplateZone): number {
    return getZonePage(zone, this.previewPage, this.previewPageCount)
  }

  private isOnCurrentPage(zone: OcrTemplateZone): boolean {
    return isZoneOnPage(zone, this.previewPage, this.previewPageCount)
  }

  onImageLoad() {
    this.imageLoaded = true
    const img = this.imageRef.nativeElement
    this.template.source_width = img.naturalWidth
    this.template.source_height = img.naturalHeight
  }

  onOverlayMouseDown(event: MouseEvent) {
    const point = this.svgPointFromEvent(event)
    if (!point) return
    event.preventDefault()

    if (this.selectedZoneIndex !== null) {
      const handle = this.findHandleAt(point, this.selectedZoneIndex)
      if (handle) {
        this.overlayInteraction = {
          kind: 'resizing',
          zoneIndex: this.selectedZoneIndex,
          handle,
        }
        return
      }
    }

    const clickedIdx = this.findZoneAt(point)
    if (clickedIdx !== null && !event.shiftKey) {
      this.selectZone(clickedIdx)
      const zone = this.template.zones[clickedIdx]
      this.overlayInteraction = {
        kind: 'moving',
        zoneIndex: clickedIdx,
        start: {
          mouseX: point.x,
          mouseY: point.y,
          zoneX: zone.x,
          zoneY: zone.y,
        },
      }
      return
    }

    // Shift+click or click on empty area starts a new zone.
    this.overlayInteraction = {
      kind: 'drawing',
      rect: {
        startX: point.x,
        startY: point.y,
        endX: point.x,
        endY: point.y,
      },
    }
    this.selectedZoneIndex = null
  }

  onOverlayMouseMove(event: MouseEvent) {
    const point = this.svgPointFromEvent(event)
    if (!point) return

    if (this.overlayInteraction.kind === 'resizing') {
      this.applyResize(
        this.overlayInteraction.zoneIndex,
        this.overlayInteraction.handle,
        point
      )
      return
    }

    if (this.overlayInteraction.kind === 'moving') {
      moveZone(
        this.template.zones[this.overlayInteraction.zoneIndex],
        point,
        this.overlayInteraction.start,
        this.imageNaturalSize(),
        this.imageNaturalSize()
      )
      return
    }

    if (this.overlayInteraction.kind === 'drawing') {
      this.overlayInteraction.rect.endX = point.x
      this.overlayInteraction.rect.endY = point.y
      return
    }

    this.updateOverlayCursor(point)
  }

  private updateOverlayCursor(point: Point) {
    if (this.selectedZoneIndex !== null) {
      const handle = this.findHandleAt(point, this.selectedZoneIndex)
      if (handle) {
        this.overlayCursor = RESIZE_CURSOR[handle] || 'crosshair'
        return
      }
    }
    this.overlayCursor = this.findZoneAt(point) !== null ? 'move' : 'crosshair'
  }

  onOverlayMouseUp(_event: MouseEvent) {
    if (
      this.overlayInteraction.kind === 'moving' ||
      this.overlayInteraction.kind === 'resizing'
    ) {
      this.stopOverlayInteraction()
      return
    }

    if (this.overlayInteraction.kind !== 'drawing') return
    const drawingRect = this.overlayInteraction.rect
    this.stopOverlayInteraction()

    const rect = this.sourceRectFromDrawing(drawingRect)

    // Ignore tiny accidental clicks.
    if (rect.w < MIN_DRAWN_ZONE_SIZE || rect.h < MIN_DRAWN_ZONE_SIZE) {
      return
    }

    this.template.zones.push(this.createZoneFromRect(rect))
    this.selectZone(this.template.zones.length - 1)
  }

  private createZoneFromRect(rect: DisplayRect): OcrTemplateZone {
    const imageSize = this.imageNaturalSize()
    return {
      name: `Zone ${this.template.zones.length + 1}`,
      target: DEFAULT_OCR_ZONE_TARGET,
      custom_field: this.defaultCustomFieldId(),
      x: rect.x,
      y: rect.y,
      width: rect.w,
      height: rect.h,
      page: this.previewPageDisplay,
      ocr_language: DEFAULT_OCR_ZONE_LANGUAGE,
      transform: DEFAULT_OCR_ZONE_TRANSFORM,
      date_format: '',
      validation_regex: '',
      order: this.template.zones.length,
      zone_source_width: imageSize.width,
      zone_source_height: imageSize.height,
    }
  }

  private defaultCustomFieldId(): number | null {
    return this.customFields[0]?.id ?? null
  }

  @HostListener('document:mouseup')
  onDocumentMouseUp() {
    if (this.overlayInteraction.kind === 'idle') return
    this.stopOverlayInteraction()
  }

  private stopOverlayInteraction() {
    this.overlayInteraction = NO_OVERLAY_INTERACTION
    this.overlayCursor = 'crosshair'
  }

  drawingRect(): DisplayRect | null {
    return this.overlayInteraction.kind === 'drawing'
      ? this.displayRectFromDrawing(this.overlayInteraction.rect)
      : null
  }

  zoneDisplayRect(zoneIdx: number): DisplayRect | null {
    const img = this.imageRef?.nativeElement
    if (!img || !img.naturalWidth) return null
    const zone = this.template.zones[zoneIdx]
    if (!zone) return null
    if (!this.isOnCurrentPage(zone)) return null
    return getZoneDisplayRect(
      zone,
      this.imageNaturalSize(),
      this.imageNaturalSize()
    )
  }

  private findHandleAt(point: Point, zoneIdx: number): ResizeHandle | null {
    const r = this.zoneDisplayRect(zoneIdx)
    if (!r) return null
    return findHandleAt(point, r, this.overlayHandleSize())
  }

  private applyResize(zoneIndex: number, handle: ResizeHandle, point: Point) {
    const zone = this.template.zones[zoneIndex]
    if (!zone) return
    resizeZone(
      zone,
      handle,
      point,
      this.imageNaturalSize(),
      this.imageNaturalSize()
    )
  }

  private findZoneAt(point: Point): number | null {
    const img = this.imageRef.nativeElement
    if (!img.naturalWidth) return null

    return findZoneAt(
      point,
      this.template.zones,
      this.previewPage,
      this.previewPageCount,
      this.imageNaturalSize(),
      this.imageNaturalSize()
    )
  }

  overlayViewBox(): string {
    const imageSize = this.imageNaturalSize()
    return `0 0 ${imageSize.width} ${imageSize.height}`
  }

  zoneColor(index: number): string {
    return ZONE_COLORS[index % ZONE_COLORS.length]
  }

  zoneFill(index: number): string {
    return `${this.zoneColor(index)}33`
  }

  zoneLabel(zone: OcrTemplateZone, index: number): string {
    return zone.name || `Zone ${index + 1}`
  }

  zoneLabelY(rect: DisplayRect): number {
    return Math.max(this.overlayUnitSize(14), rect.y - this.overlayUnitSize(4))
  }

  resizeHandles(rect: DisplayRect): ResizeHandleMarker[] {
    return [
      { handle: 'nw', x: rect.x, y: rect.y },
      { handle: 'n', x: rect.x + rect.w / 2, y: rect.y },
      { handle: 'ne', x: rect.x + rect.w, y: rect.y },
      { handle: 'w', x: rect.x, y: rect.y + rect.h / 2 },
      { handle: 'e', x: rect.x + rect.w, y: rect.y + rect.h / 2 },
      { handle: 'sw', x: rect.x, y: rect.y + rect.h },
      { handle: 's', x: rect.x + rect.w / 2, y: rect.y + rect.h },
      { handle: 'se', x: rect.x + rect.w, y: rect.y + rect.h },
    ]
  }

  overlayHandleSize(): number {
    return this.overlayUnitSize(HANDLE_SIZE)
  }

  overlayFontSize(): number {
    return this.overlayUnitSize(12)
  }

  overlayUnitSize(screenPixels: number): number {
    const img = this.imageRef?.nativeElement
    if (!img?.naturalWidth || !img.clientWidth) return screenPixels
    return (screenPixels * img.naturalWidth) / img.clientWidth
  }

  private svgPointFromEvent(event: MouseEvent): Point | null {
    const svg = this.overlayRef?.nativeElement
    const matrix = svg?.getScreenCTM()
    if (!svg || !matrix) return null

    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY

    const svgPoint = point.matrixTransform(matrix.inverse())
    return { x: svgPoint.x, y: svgPoint.y }
  }

  private displayRectFromDrawing(rect: DrawingRect): DisplayRect {
    return {
      x: Math.min(rect.startX, rect.endX),
      y: Math.min(rect.startY, rect.endY),
      w: Math.abs(rect.endX - rect.startX),
      h: Math.abs(rect.endY - rect.startY),
    }
  }

  private sourceRectFromDrawing(rect: DrawingRect): DisplayRect {
    const displayRect = this.displayRectFromDrawing(rect)
    return {
      x: Math.round(displayRect.x),
      y: Math.round(displayRect.y),
      w: Math.round(displayRect.w),
      h: Math.round(displayRect.h),
    }
  }

  private imageNaturalSize() {
    const img = this.imageRef.nativeElement
    return { width: img.naturalWidth, height: img.naturalHeight }
  }

  removeZone(index: number) {
    this.template.zones.splice(index, 1)
    if (this.selectedZoneIndex === index) {
      this.selectedZoneIndex = null
    } else if (this.selectedZoneIndex > index) {
      this.selectedZoneIndex--
    }
  }

  selectZone(index: number) {
    this.selectedZoneIndex = index
    this.activeTab = 'zone'
    this.zoneTestResult = null
    const zone = this.template.zones[index]
    if (zone) {
      this.seedCombineDefault(zone)
      this.goToPage(this.zonePage(zone) - 1)
    }
  }

  testZone() {
    const zone = this.selectedZone
    if (!zone || !this.previewDocId) return
    this.zoneTesting = true
    this.zoneTestResult = null
    this.templateService
      .testZone(this.previewDocId, this.zoneTestRequest(zone))
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.zoneTestResult = res
          this.zoneTesting = false
        },
        error: (err) => {
          this.zoneTestResult = {
            error: err.error?.error || $localize`Test failed`,
          }
          this.zoneTesting = false
        },
      })
  }

  private zoneTestRequest(zone: OcrTemplateZone): ZoneTestRequest {
    return {
      name: zone.name,
      x: zone.x,
      y: zone.y,
      width: zone.width,
      height: zone.height,
      page: zone.page ?? 1,
      ocr_language: zone.ocr_language,
      transform: zone.transform,
      date_format: zone.date_format,
      validation_regex: zone.validation_regex,
      zone_source_width: zone.zone_source_width,
      zone_source_height: zone.zone_source_height,
    }
  }

  deleteSelectedZone() {
    if (this.selectedZoneIndex === null) return
    this.removeZone(this.selectedZoneIndex)
    this.activeTab = 'zones'
  }

  save() {
    this.saving = true
    this.pruneCombineFormats()
    this.template.sample_document = this.previewDocId
    const obs = this.isNew
      ? this.templateService.create(this.template)
      : this.templateService.update(this.template)

    obs.pipe(takeUntil(this.destroy$)).subscribe({
      next: (saved) => {
        const idx = this.selectedZoneIndex
        this.template = saved
        this.isNew = false
        this.selectedZoneIndex = idx
        this.saving = false
        this.toastService.showInfo($localize`OCR template saved.`)
      },
      error: (e) => {
        this.saving = false
        this.toastService.showError($localize`Error saving OCR template.`, e)
      },
    })
  }

  private ocrLangCache = new WeakMap<
    OcrTemplateZone,
    { src: string; arr: string[] }
  >()

  ocrLanguageArray(zone: OcrTemplateZone): string[] {
    const src = zone.ocr_language || ''
    const cached = this.ocrLangCache.get(zone)
    if (cached && cached.src === src) return cached.arr
    const arr = src ? src.split('+').filter(Boolean) : []
    this.ocrLangCache.set(zone, { src, arr })
    return arr
  }

  setOcrLanguages(zone: OcrTemplateZone, langs: string[]) {
    zone.ocr_language = (langs || []).join('+')
    this.ocrLangCache.set(zone, {
      src: zone.ocr_language,
      arr: langs ? [...langs] : [],
    })
  }

  getCustomFieldName(id: number): string {
    const cf = this.customFields.find((f) => f.id === id)
    return cf ? cf.name : `Field #${id}`
  }

  /** Value bound to the field select: a built-in id string or a custom-field id. */
  zoneFieldValue(zone: OcrTemplateZone): ZoneFieldSelection {
    const target = zone.target || DEFAULT_OCR_ZONE_TARGET
    return target === OCR_ZONE_TARGET.CustomField ? zone.custom_field : target
  }

  setZoneField(zone: OcrTemplateZone, value: ZoneFieldSelection) {
    if (isOcrBuiltinTarget(value)) {
      zone.target = value
      zone.custom_field = null
    } else {
      zone.target = OCR_ZONE_TARGET.CustomField
      zone.custom_field = typeof value === 'number' ? value : null
    }
    this.seedCombineDefault(zone)
  }

  fieldKeyFor(zone: OcrTemplateZone): string | null {
    const v = this.zoneFieldValue(zone)
    return v === null || v === undefined ? null : String(v)
  }

  zonesForField(zone: OcrTemplateZone): OcrTemplateZone[] {
    const key = this.fieldKeyFor(zone)
    if (!key) return []
    return this.template.zones.filter((z) => this.fieldKeyFor(z) === key)
  }

  isFieldShared(zone: OcrTemplateZone): boolean {
    return this.zonesForField(zone).length > 1
  }

  getCombineFormat(zone: OcrTemplateZone): string {
    const key = this.fieldKeyFor(zone)
    return (key && this.template.combine_formats?.[key]) || ''
  }

  setCombineFormat(zone: OcrTemplateZone, value: string) {
    const key = this.fieldKeyFor(zone)
    if (!key) return
    this.template.combine_formats ??= {}
    this.template.combine_formats[key] = value
  }

  insertCombineToken(zone: OcrTemplateZone, tokenZone: OcrTemplateZone) {
    const token = `{${tokenZone.name}}`
    const current = this.getCombineFormat(zone)
    const sep = current && !current.endsWith(' ') ? ' ' : ''
    this.setCombineFormat(zone, `${current}${sep}${token}`)
  }

  private seedCombineDefault(zone: OcrTemplateZone) {
    const key = this.fieldKeyFor(zone)
    if (!key) return
    const shared = this.zonesForField(zone)
    if (shared.length <= 1) return
    this.template.combine_formats ??= {}
    if (!this.template.combine_formats[key]) {
      this.template.combine_formats[key] = shared
        .map((z) => `{${z.name}}`)
        .join(' ')
    }
  }

  private pruneCombineFormats() {
    const formats = this.template.combine_formats
    if (!formats) return
    const counts = new Map<string, number>()
    for (const z of this.template.zones) {
      const key = this.fieldKeyFor(z)
      if (key) counts.set(key, (counts.get(key) ?? 0) + 1)
    }
    for (const key of Object.keys(formats)) {
      if ((counts.get(key) ?? 0) <= 1) delete formats[key]
    }
  }

  /** Value bound to the date-format select: a preset, '' (auto), or 'custom'. */
  dateFormatChoice(zone: OcrTemplateZone): string {
    return this.usesCustomDateFormat(zone)
      ? CUSTOM_DATE_FORMAT_CHOICE
      : zone.date_format || ''
  }

  setDateFormatChoice(zone: OcrTemplateZone, value: string) {
    if (value === CUSTOM_DATE_FORMAT_CHOICE) {
      this.customDateFormatZones.add(zone)
      zone.date_format ||= ''
    } else {
      this.customDateFormatZones.delete(zone)
      zone.date_format = value
    }
  }

  usesCustomDateFormat(zone: OcrTemplateZone): boolean {
    return (
      this.customDateFormatZones.has(zone) ||
      (!!zone.date_format &&
        !this.dateFormatOptions.some(
          (option) => option.id === zone.date_format
        ))
    )
  }

  getZoneTargetName(zone: OcrTemplateZone): string {
    const target = zone.target || DEFAULT_OCR_ZONE_TARGET
    if (target === OCR_ZONE_TARGET.CustomField) {
      return zone.custom_field
        ? this.getCustomFieldName(zone.custom_field)
        : $localize`(no field)`
    }
    return this.builtinTargets.find((t) => t.id === target)?.name ?? target
  }

  getDocumentTypeName(id: number): string {
    const dt = this.documentTypes.find((d) => d.id === id)
    return dt ? dt.name : `Type #${id}`
  }

  openQuickCreate(zoneIndex: number | null) {
    if (zoneIndex === null) return
    this.quickCreateForZoneIndex = zoneIndex
    this.quickCreateName = this.template.zones[zoneIndex]?.name || ''
    this.quickCreateType = CustomFieldDataType.String
    this.showQuickCreate = true
  }

  cancelQuickCreate() {
    this.showQuickCreate = false
    this.quickCreateForZoneIndex = null
  }

  submitQuickCreate() {
    if (!this.quickCreateName.trim()) return

    this.templateService
      .quickCreateField(this.quickCreateName.trim(), this.quickCreateType)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (result) => {
          this.customFieldsService.clearCache()
          this.customFieldsService
            .listAll()
            .pipe(takeUntil(this.destroy$))
            .subscribe((r) => {
              this.customFields = r.results
              if (this.quickCreateForZoneIndex !== null) {
                this.template.zones[this.quickCreateForZoneIndex].custom_field =
                  result.id
                this.template.zones[this.quickCreateForZoneIndex].target =
                  OCR_ZONE_TARGET.CustomField
              }
              this.showQuickCreate = false
              this.quickCreateForZoneIndex = null
            })
        },
        error: (err) => {
          this.toastService.showError(
            $localize`Failed to create custom field.`,
            err
          )
        },
      })
  }

  ngOnDestroy() {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
