import { CommonModule } from '@angular/common'
import {
  Component,
  computed,
  ElementRef,
  EventEmitter,
  HostListener,
  inject,
  Input,
  OnDestroy,
  OnInit,
  Output,
  signal,
  ViewChild,
} from '@angular/core'
import { FormsModule } from '@angular/forms'
import {
  NgbActiveModal,
  NgbModal,
  NgbNavModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import { CustomFieldEditDialogComponent } from 'src/app/components/common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { EditDialogMode } from 'src/app/components/common/edit-dialog/edit-dialog.component'
import { DocumentLinkComponent } from 'src/app/components/common/input/document-link/document-link.component'
import { CheckComponent } from 'src/app/components/common/input/check/check.component'
import { NumberComponent } from 'src/app/components/common/input/number/number.component'
import {
  PermissionsFormComponent,
  PermissionsFormObject,
} from 'src/app/components/common/input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from 'src/app/components/common/input/select/select.component'
import { SwitchComponent } from 'src/app/components/common/input/switch/switch.component'
import { TextComponent } from 'src/app/components/common/input/text/text.component'
import { CustomField } from 'src/app/data/custom-field'
import {
  MATCH_ANY,
  MATCH_AUTO,
  MATCH_NONE,
  MATCHING_ALGORITHMS,
} from 'src/app/data/matching-model'
import {
  DEFAULT_OCR_ZONE_LANGUAGE,
  getZoneFieldKey,
  OCR_BUILTIN_TARGETS,
  OCR_SUPPORTED_FIELD_TYPES,
  OcrTemplate,
  OcrTemplateZone,
  OcrZoneTarget,
  OcrZoneTestResult,
  OcrZoneTransform,
  ZoneTestRequest,
} from 'src/app/data/ocr-template'
import { SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { User } from 'src/app/data/user'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { UserService } from 'src/app/services/rest/user.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { OcrTemplateEditorZoneListComponent } from './ocr-template-editor-zone-list/ocr-template-editor-zone-list.component'
import {
  DisplayRect,
  DrawingRect,
  findHandleAt,
  findZoneAt,
  getResizeHandles,
  getZoneColor,
  getZoneDisplayRect,
  getZonePage,
  HANDLE_SIZE,
  isZoneOnPage,
  MIN_ZONE_SIZE,
  MoveStart,
  moveZone,
  Point,
  ResizeHandle,
  resizeZone,
} from './zone-geometry'

type ActiveTab = 'template' | 'zones'
type ZoneFieldSelection = OcrZoneTarget | number | null
type OverlayInteraction =
  | { kind: 'idle' }
  | { kind: 'drawing'; pointerId: number; rect: DrawingRect }
  | { kind: 'moving'; pointerId: number; zoneIndex: number; start: MoveStart }
  | {
      kind: 'resizing'
      pointerId: number
      zoneIndex: number
      handle: ResizeHandle
    }
interface ZoneTest {
  zone: OcrTemplateZone
  /** The sample document and zone settings the result was produced from. */
  key: string
  result: OcrZoneTestResult | null
}

export const ZONE_TRANSFORM_OPTIONS = [
  { id: OcrZoneTransform.None, name: $localize`None` },
  { id: OcrZoneTransform.Strip, name: $localize`Strip whitespace` },
  { id: OcrZoneTransform.Uppercase, name: $localize`Uppercase` },
  { id: OcrZoneTransform.Lowercase, name: $localize`Lowercase` },
  { id: OcrZoneTransform.Numeric, name: $localize`Numeric only` },
  {
    id: OcrZoneTransform.StripPunctuation,
    name: $localize`Remove leading/trailing punctuation`,
  },
  { id: OcrZoneTransform.Date, name: $localize`Parse date` },
  { id: OcrZoneTransform.QrCode, name: $localize`Read QR/barcode` },
]

export const ZONE_LANGUAGE_OPTIONS = [
  { id: 'eng', name: $localize`English` },
  { id: 'deu', name: $localize`German` },
  { id: 'fra', name: $localize`French` },
  { id: 'ita', name: $localize`Italian` },
  { id: 'spa', name: $localize`Spanish` },
  { id: 'por', name: $localize`Portuguese` },
  { id: 'nld', name: $localize`Dutch` },
]

const TEMPLATE_MATCHING_ALGORITHMS = MATCHING_ALGORITHMS.filter(
  (algorithm) => algorithm.id !== MATCH_AUTO
)

const NO_OVERLAY_INTERACTION: OverlayInteraction = { kind: 'idle' }
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
  imports: [
    DocumentLinkComponent,
    NumberComponent,
    TextComponent,
    CheckComponent,
    SelectComponent,
    SwitchComponent,
    CommonModule,
    FormsModule,
    NgbNavModule,
    NgxBootstrapIconsModule,
    OcrTemplateEditorZoneListComponent,
    PermissionsFormComponent,
    IfOwnerDirective,
  ],
  templateUrl: './ocr-template-editor.component.html',
  styleUrls: ['./ocr-template-editor.component.scss'],
})
export class OcrTemplateEditorComponent implements OnInit, OnDestroy {
  public readonly activeModal = inject(NgbActiveModal)
  private readonly templateService = inject(OcrTemplateService)
  private readonly customFieldsService = inject(CustomFieldsService)
  private readonly documentService = inject(DocumentService)
  private readonly toastService = inject(ToastService)
  private readonly modalService = inject(NgbModal)
  private readonly userService = inject(UserService)
  private readonly settingsService = inject(SettingsService)
  private readonly permissionsService = inject(PermissionsService)
  private readonly destroy$ = new Subject<void>()
  private readonly cancelZoneTest$ = new Subject<void>()

  @Input() object: OcrTemplate
  @Output() public readonly succeeded = new EventEmitter<OcrTemplate>()
  @Output() public readonly failed = new EventEmitter()

  @ViewChild('zoneOverlay') overlayRef: ElementRef<SVGSVGElement>
  imageRef: ElementRef<HTMLImageElement>
  private previewResizeObserver: ResizeObserver | null = null
  private readonly overlayScale = signal(1)

  @ViewChild('pageImage')
  set pageImage(ref: ElementRef<HTMLImageElement> | undefined) {
    this.previewResizeObserver?.disconnect()
    this.imageRef = ref
    if (!ref) return
    this.previewResizeObserver = new ResizeObserver(() => {
      const image = ref.nativeElement
      if (image.naturalWidth && image.clientWidth) {
        this.overlayScale.set(image.naturalWidth / image.clientWidth)
      }
    })
    this.previewResizeObserver.observe(ref.nativeElement)
  }

  template: OcrTemplate = {
    id: null,
    name: '',
    match: '',
    matching_algorithm: MATCH_ANY,
    is_insensitive: true,
    sample_document: null,
    source_width: 0,
    source_height: 0,
    enabled: true,
    combine_formats: {},
    zones: [],
  }

  public readonly customFields = signal<CustomField[]>([])
  public readonly fieldItems = computed<
    { id: ZoneFieldSelection; name: string }[]
  >(() => [
    ...OCR_BUILTIN_TARGETS,
    ...this.customFields()
      .filter((field) => OCR_SUPPORTED_FIELD_TYPES.includes(field.data_type))
      .map((field) => ({ id: field.id, name: field.name })),
  ])
  public readonly users = signal<User[]>([])
  permissionsForm: PermissionsFormObject = {}
  public readonly OcrZoneTransform = OcrZoneTransform
  public readonly saving = signal(false)

  /** Bound to the document picker, which works with id arrays. */
  sampleDocumentIds: number[] = []
  previewPage = 0
  public readonly previewPageCount = signal<number | null>(null)
  public readonly pageLoaded = signal(false)
  public readonly pageFailed = signal(false)
  zoom = 1

  get previewDocId(): number | null {
    return this.sampleDocumentIds[0] ?? null
  }

  get pageImageUrl(): string | null {
    return this.previewDocId
      ? this.templateService.getPageImageUrl(
          this.previewDocId,
          this.previewPage
        )
      : null
  }

  get transformOptions() {
    return ZONE_TRANSFORM_OPTIONS
  }

  get languageOptions() {
    return ZONE_LANGUAGE_OPTIONS
  }

  get matchingAlgorithms() {
    return TEMPLATE_MATCHING_ALGORITHMS
  }

  get patternRequired(): boolean {
    return (
      this.template.matching_algorithm !== MATCH_AUTO &&
      this.template.matching_algorithm !== MATCH_NONE
    )
  }

  public get previewPageDisplay(): number {
    return this.previewPage + 1
  }

  public set previewPageDisplay(value: number) {
    this.goToPage(value - 1)
  }

  activeTab: ActiveTab = 'template'

  selectedZoneIndex: number | null = null
  private overlayInteraction: OverlayInteraction = NO_OVERLAY_INTERACTION
  overlayCursor = 'crosshair'

  private readonly zoneTest = signal<ZoneTest | null>(null)

  get zoneTestResult(): OcrZoneTestResult | null {
    return this.isCurrentZoneTest() ? this.zoneTest().result : null
  }

  get zoneTesting(): boolean {
    return this.isCurrentZoneTest() && this.zoneTest().result === null
  }

  get selectedZone(): OcrTemplateZone | null {
    return this.selectedZoneIndex !== null
      ? (this.template.zones[this.selectedZoneIndex] ?? null)
      : null
  }

  private initialState = ''

  get isDirty(): boolean {
    return this.editorState() !== this.initialState
  }

  private editorState(): string {
    const formats = Object.entries(this.template.combine_formats ?? {}).filter(
      ([, format]) => format
    )
    return JSON.stringify({
      ...this.template,
      combine_formats: Object.fromEntries(formats),
      sample_document: this.previewDocId ?? null,
      permissions_form: this.permissionsForm,
    })
  }

  get dialogTitle(): string {
    return this.template.id
      ? $localize`Edit OCR Template`
      : $localize`New OCR Template`
  }

  ngOnInit() {
    this.userService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => this.users.set(r.results))
    this.customFieldsService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => {
        this.customFields.set(r.results)
      })

    if (this.object) {
      this.template = {
        ...this.object,
        zones: this.object.zones.map((zone) => ({ ...zone })),
        combine_formats: { ...this.object.combine_formats },
      }
      if (this.template.sample_document) {
        this.setSampleDocument([this.template.sample_document])
      }
    }
    const permissions = this.object?.permissions
    this.permissionsForm = this.object
      ? {
          owner: this.object.owner,
          set_permissions: {
            view: {
              users: [...(permissions?.view.users ?? [])],
              groups: [...(permissions?.view.groups ?? [])],
            },
            change: {
              users: [...(permissions?.change.users ?? [])],
              groups: [...(permissions?.change.groups ?? [])],
            },
          },
        }
      : {
          owner: this.settingsService.get(SETTINGS_KEYS.DEFAULT_PERMS_OWNER),
          set_permissions: {
            view: {
              users: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_VIEW_USERS
              ),
              groups: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_VIEW_GROUPS
              ),
            },
            change: {
              users: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_EDIT_USERS
              ),
              groups: this.settingsService.get(
                SETTINGS_KEYS.DEFAULT_PERMS_EDIT_GROUPS
              ),
            },
          },
        }
    this.initialState = this.editorState()
  }

  setSampleDocument(ids: number[]) {
    const id = ids.at(-1)
    this.sampleDocumentIds = id ? [id] : []
    this.previewPage = 0
    this.previewPageCount.set(null)
    this.resetPage()
    if (!id) return
    this.documentService
      .get(id)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (doc) => {
          if (this.previewDocId !== id) return
          this.previewPageCount.set(doc.page_count ?? null)
        },
        error: () => {
          if (this.previewDocId === id) this.pageFailed.set(true)
        },
      })
  }

  private resetPage() {
    this.stopOverlayInteraction()
    this.clearZoneTest()
    this.pageLoaded.set(false)
    this.pageFailed.set(false)
  }

  goToPage(page: number) {
    if (!Number.isFinite(page)) return
    const pageCount = this.previewPageCount()
    const max = pageCount ? pageCount - 1 : page
    const clamped = Math.max(0, Math.min(Math.trunc(page), max))
    if (clamped === this.previewPage) return
    this.previewPage = clamped
    this.resetPage()
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
    return getZonePage(zone, this.previewPage, this.previewPageCount())
  }

  isLastPageZone(zone: OcrTemplateZone): boolean {
    return zone.page === -1
  }

  setLastPageZone(zone: OcrTemplateZone, lastPage: boolean) {
    zone.page = lastPage ? -1 : this.previewPage + 1
  }

  private isOnCurrentPage(zone: OcrTemplateZone): boolean {
    return isZoneOnPage(zone, this.previewPage, this.previewPageCount())
  }

  onImageLoad() {
    this.pageLoaded.set(true)
    const img = this.imageRef.nativeElement
    this.template.source_width = img.naturalWidth
    this.template.source_height = img.naturalHeight
  }

  onImageError() {
    this.stopOverlayInteraction()
    this.pageFailed.set(true)
  }

  @HostListener('document:keydown.escape')
  cancelDrawing() {
    this.stopOverlayInteraction()
  }

  onOverlayPointerDown(event: PointerEvent) {
    if (this.saving()) return
    if (event.button !== 0 || this.overlayInteraction.kind !== 'idle') return
    const point = this.svgPointFromEvent(event)
    if (!this.pageLoaded() || !point) return
    event.preventDefault()

    if (this.selectedZoneIndex !== null) {
      const handle = this.handleAt(point, this.selectedZoneIndex)
      if (handle) {
        this.overlayInteraction = {
          kind: 'resizing',
          pointerId: event.pointerId,
          zoneIndex: this.selectedZoneIndex,
          handle,
        }
        this.overlayRef.nativeElement.setPointerCapture(event.pointerId)
        return
      }
    }

    const clickedIdx = this.zoneIndexAt(point)
    if (clickedIdx !== null) {
      this.selectZone(clickedIdx)
      const zone = this.template.zones[clickedIdx]
      this.overlayInteraction = {
        kind: 'moving',
        pointerId: event.pointerId,
        zoneIndex: clickedIdx,
        start: {
          mouseX: point.x,
          mouseY: point.y,
          zoneX: zone.x,
          zoneY: zone.y,
        },
      }
      this.overlayRef.nativeElement.setPointerCapture(event.pointerId)
      return
    }

    // Empty space: start drawing a new zone. A click without a drag just clears
    // the selection (see onOverlayPointerUp).
    this.clearZoneTest()
    this.selectedZoneIndex = null
    this.overlayInteraction = {
      kind: 'drawing',
      pointerId: event.pointerId,
      rect: {
        startX: point.x,
        startY: point.y,
        endX: point.x,
        endY: point.y,
      },
    }
    this.overlayRef.nativeElement.setPointerCapture(event.pointerId)
  }

  onOverlayPointerMove(event: PointerEvent) {
    if (
      this.overlayInteraction.kind !== 'idle' &&
      this.overlayInteraction.pointerId !== event.pointerId
    )
      return
    const point = this.svgPointFromEvent(event)
    if (!point) return

    if (this.overlayInteraction.kind === 'resizing') {
      resizeZone(
        this.template.zones[this.overlayInteraction.zoneIndex],
        this.overlayInteraction.handle,
        point,
        this.imageNaturalSize()
      )
      return
    }

    if (this.overlayInteraction.kind === 'moving') {
      moveZone(
        this.template.zones[this.overlayInteraction.zoneIndex],
        point,
        this.overlayInteraction.start,
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
      const handle = this.handleAt(point, this.selectedZoneIndex)
      if (handle) {
        this.overlayCursor = RESIZE_CURSOR[handle]
        return
      }
    }
    this.overlayCursor = this.zoneIndexAt(point) !== null ? 'move' : 'crosshair'
  }

  onOverlayPointerUp(event: PointerEvent) {
    if (this.overlayInteraction.kind === 'idle') return
    if (this.overlayInteraction.pointerId !== event.pointerId) return
    this.onOverlayPointerMove(event)
    const interaction = this.overlayInteraction
    this.stopOverlayInteraction()
    if (interaction.kind !== 'drawing') return

    const rect = this.sourceRectFromDrawing(interaction.rect)

    // Ignore tiny accidental clicks.
    if (rect.w < MIN_ZONE_SIZE || rect.h < MIN_ZONE_SIZE) {
      return
    }

    this.template.zones.push(this.createZoneFromRect(rect))
    this.selectZone(this.template.zones.length - 1)
  }

  private createZoneFromRect(rect: DisplayRect): OcrTemplateZone {
    const imageSize = this.imageNaturalSize()
    return {
      name: `Zone ${this.template.zones.length + 1}`,
      target: OcrZoneTarget.CustomField,
      custom_field: null,
      x: rect.x,
      y: rect.y,
      width: rect.w,
      height: rect.h,
      page: this.previewPageDisplay,
      ocr_language: DEFAULT_OCR_ZONE_LANGUAGE,
      transform: OcrZoneTransform.Strip,
      date_format: '',
      validation_regex: '',
      order: this.template.zones.length,
      zone_source_width: imageSize.width,
      zone_source_height: imageSize.height,
    }
  }

  onOverlayPointerCancel(event: PointerEvent) {
    if (this.overlayInteraction.kind === 'idle') return
    if (this.overlayInteraction.pointerId !== event.pointerId) return
    this.stopOverlayInteraction()
  }

  private stopOverlayInteraction() {
    const interaction = this.overlayInteraction
    this.overlayInteraction = NO_OVERLAY_INTERACTION
    this.overlayCursor = 'crosshair'
    const overlay = this.overlayRef?.nativeElement
    if (
      interaction.kind !== 'idle' &&
      overlay?.hasPointerCapture(interaction.pointerId)
    ) {
      overlay.releasePointerCapture(interaction.pointerId)
    }
  }

  drawingRect(): DisplayRect | null {
    return this.overlayInteraction.kind === 'drawing'
      ? this.displayRectFromDrawing(this.overlayInteraction.rect)
      : null
  }

  /** The zone's rectangle on the overlay, or null if it's on another page. */
  zoneDisplayRect(zoneIndex: number): DisplayRect | null {
    const zone = this.template.zones[zoneIndex]
    if (!this.isOnCurrentPage(zone)) return null
    return getZoneDisplayRect(zone, this.imageNaturalSize())
  }

  private handleAt(point: Point, zoneIndex: number): ResizeHandle | null {
    const rect = this.zoneDisplayRect(zoneIndex)
    return rect ? findHandleAt(point, rect, this.overlayHandleSize()) : null
  }

  private zoneIndexAt(point: Point): number | null {
    return findZoneAt(
      point,
      this.template.zones,
      this.previewPage,
      this.previewPageCount(),
      this.imageNaturalSize()
    )
  }

  overlayViewBox(): string {
    const imageSize = this.imageNaturalSize()
    return `0 0 ${imageSize.width} ${imageSize.height}`
  }

  public readonly zoneColor = getZoneColor

  zoneLabel(zone: OcrTemplateZone, index: number): string {
    return zone.name || `Zone ${index + 1}`
  }

  zoneLabelY(rect: DisplayRect): number {
    return Math.max(this.overlayUnitSize(14), rect.y - this.overlayUnitSize(4))
  }

  public readonly resizeHandles = getResizeHandles

  overlayHandleSize(): number {
    return this.overlayUnitSize(HANDLE_SIZE)
  }

  overlayFontSize(): number {
    return this.overlayUnitSize(12)
  }

  overlayUnitSize(screenPixels: number): number {
    return screenPixels * this.overlayScale()
  }

  private svgPointFromEvent(event: MouseEvent): Point | null {
    const svg = this.overlayRef?.nativeElement
    const matrix = svg?.getScreenCTM()
    if (!svg || !matrix) return null

    const point = svg.createSVGPoint()
    point.x = event.clientX
    point.y = event.clientY

    const svgPoint = point.matrixTransform(matrix.inverse())
    const size = this.imageNaturalSize()
    return {
      x: Math.max(0, Math.min(svgPoint.x, size.width)),
      y: Math.max(0, Math.min(svgPoint.y, size.height)),
    }
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
    this.stopOverlayInteraction()
    this.clearZoneTest()
    this.template.zones.splice(index, 1)
    if (this.selectedZoneIndex === index) {
      this.selectedZoneIndex = null
    } else if (this.selectedZoneIndex > index) {
      this.selectedZoneIndex--
    }
  }

  selectZone(index: number) {
    this.selectedZoneIndex = index
    this.activeTab = 'zones'
    this.clearZoneTest()
    const zone = this.template.zones[index]
    if (zone) {
      this.goToPage(this.zonePage(zone) - 1)
    }
  }

  deselectZone() {
    this.selectedZoneIndex = null
    this.clearZoneTest()
  }

  testZone() {
    const zone = this.selectedZone
    if (!zone || !this.previewDocId) return
    this.clearZoneTest()
    const test: ZoneTest = { zone, key: this.zoneTestKey(zone), result: null }
    this.zoneTest.set(test)
    this.templateService
      .testZone(this.previewDocId, this.zoneTestRequest(zone))
      .pipe(takeUntil(this.destroy$), takeUntil(this.cancelZoneTest$))
      .subscribe({
        next: (res) => this.zoneTest.set({ ...test, result: res }),
        error: (err) =>
          this.zoneTest.set({
            ...test,
            result: { error: err.error?.error || $localize`Test failed` },
          }),
      })
  }

  private clearZoneTest() {
    this.cancelZoneTest$.next()
    this.zoneTest.set(null)
  }

  /** A result is stale once its zone, settings or sample document change. */
  private isCurrentZoneTest(): boolean {
    const test = this.zoneTest()
    return (
      test?.zone === this.selectedZone &&
      test.key === this.zoneTestKey(test.zone)
    )
  }

  private zoneTestKey(zone: OcrTemplateZone): string {
    return JSON.stringify([this.previewDocId, this.zoneTestRequest(zone)])
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

  save() {
    if (this.saving()) return
    this.stopOverlayInteraction()
    this.saving.set(true)
    this.pruneCombineFormats()
    this.template.sample_document = this.previewDocId
    const payload = this.permissionsService.currentUserOwnsObject(this.object)
      ? { ...this.template, ...this.permissionsForm }
      : this.template
    const obs = this.template.id
      ? this.templateService.update(payload)
      : this.templateService.create(payload)

    obs.pipe(takeUntil(this.destroy$)).subscribe({
      next: (saved) => {
        this.activeModal.close()
        this.succeeded.emit(saved)
      },
      error: (e) => {
        this.saving.set(false)
        this.failed.emit(e)
      },
    })
  }

  // ng-select needs a stable array between change detection runs, so the
  // split language list is cached per zone until ocr_language changes.
  private readonly ocrLanguageCache = new WeakMap<
    OcrTemplateZone,
    { language: string; languages: string[] }
  >()

  ocrLanguageArray(zone: OcrTemplateZone): string[] {
    const language = zone.ocr_language || ''
    const cached = this.ocrLanguageCache.get(zone)
    if (cached?.language === language) return cached.languages
    const languages = language.split('+').filter(Boolean)
    this.ocrLanguageCache.set(zone, { language, languages })
    return languages
  }

  setOcrLanguages(zone: OcrTemplateZone, langs: string[]) {
    zone.ocr_language = (langs ?? []).join('+')
  }

  /** The field select's value: a built-in target, or a custom field id. */
  zoneFieldValue(zone: OcrTemplateZone): ZoneFieldSelection {
    return zone.target === OcrZoneTarget.CustomField
      ? zone.custom_field
      : zone.target
  }

  setZoneField(zone: OcrTemplateZone, value: ZoneFieldSelection) {
    if (typeof value === 'string') {
      zone.target = value
      zone.custom_field = null
    } else {
      zone.target = OcrZoneTarget.CustomField
      zone.custom_field = value
    }
  }

  zonesForField(zone: OcrTemplateZone): OcrTemplateZone[] {
    const key = getZoneFieldKey(zone)
    if (!key) return []
    return this.template.zones.filter((z) => getZoneFieldKey(z) === key)
  }

  isFieldShared(zone: OcrTemplateZone): boolean {
    return this.zonesForField(zone).length > 1
  }

  renameZone(zone: OcrTemplateZone, name: string) {
    const oldName = zone.name.trim()
    const format = this.getCombineFormat(zone)
    if (format) {
      this.setCombineFormat(
        zone,
        format.replace(/\{([^{}]*)\}/g, (token, tokenName: string) =>
          tokenName.trim() === oldName ? `{${name}}` : token
        )
      )
    }
    zone.name = name
  }

  getCombineFormat(zone: OcrTemplateZone): string {
    return this.template.combine_formats?.[getZoneFieldKey(zone)] ?? ''
  }

  setCombineFormat(zone: OcrTemplateZone, value: string) {
    const key = getZoneFieldKey(zone)
    if (!key) return
    this.template.combine_formats ??= {}
    this.template.combine_formats[key] = value
  }

  defaultCombineFormat(zone: OcrTemplateZone): string {
    return this.zonesForField(zone)
      .map((z) => `{${z.name}}`)
      .join(' ')
  }

  insertCombineToken(zone: OcrTemplateZone, tokenZone: OcrTemplateZone) {
    const current = this.getCombineFormat(zone)
    const sep = current && !current.endsWith(' ') ? ' ' : ''
    this.setCombineFormat(zone, `${current}${sep}{${tokenZone.name}}`)
  }

  /** Drop formats that are empty or whose field no longer has several zones. */
  private pruneCombineFormats() {
    const formats = this.template.combine_formats
    if (!formats) return
    const keys = this.template.zones.map(getZoneFieldKey)
    for (const [key, format] of Object.entries(formats)) {
      if (!format || keys.filter((k) => k === key).length < 2) {
        delete formats[key]
      }
    }
  }

  createField(name?: string) {
    const zone = this.selectedZone
    const modal = this.modalService.open(CustomFieldEditDialogComponent)
    modal.componentInstance.dialogMode.set(EditDialogMode.CREATE)
    modal.componentInstance.object = { name: name || zone?.name }
    modal.componentInstance.succeeded
      .pipe(takeUntil(this.destroy$))
      .subscribe((field: CustomField) => {
        this.toastService.showSuccess($localize`Saved field "${field.name}".`)
        this.customFieldsService.clearCache()
        this.customFieldsService
          .listAll()
          .pipe(takeUntil(this.destroy$))
          .subscribe((r) => {
            if (zone && OCR_SUPPORTED_FIELD_TYPES.includes(field.data_type)) {
              this.setZoneField(zone, field.id)
            }
            this.customFields.set(r.results)
          })
      })
    modal.componentInstance.failed
      .pipe(takeUntil(this.destroy$))
      .subscribe((e) => {
        this.toastService.showError($localize`Error saving field.`, e)
      })
  }

  ngOnDestroy() {
    this.previewResizeObserver?.disconnect()
    this.cancelZoneTest$.complete()
    this.destroy$.next()
    this.destroy$.complete()
  }
}
