import {
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewInit,
  inject,
} from '@angular/core'
import { CommonModule } from '@angular/common'
import { FormsModule } from '@angular/forms'
import { ActivatedRoute, Router, RouterModule } from '@angular/router'
import { NgbNavModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { Subject, takeUntil } from 'rxjs'
import {
  OcrTemplate,
  OcrTemplateZone,
  TRANSFORM_OPTIONS,
} from 'src/app/data/ocr-template'
import { CustomField } from 'src/app/data/custom-field'
import { OcrTemplateService } from 'src/app/services/rest/ocr-template.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ToastService } from 'src/app/services/toast.service'
import { PageHeaderComponent } from '../../../common/page-header/page-header.component'

interface DrawingRect {
  startX: number
  startY: number
  endX: number
  endY: number
}

@Component({
  selector: 'pngx-ocr-template-editor',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    NgbNavModule,
    NgxBootstrapIconsModule,
    PageHeaderComponent,
  ],
  templateUrl: './ocr-template-editor.component.html',
  styleUrls: ['./ocr-template-editor.component.scss'],
})
export class OcrTemplateEditorComponent
  implements OnInit, OnDestroy, AfterViewInit
{
  private readonly route = inject(ActivatedRoute)
  private readonly router = inject(Router)
  private readonly templateService = inject(OcrTemplateService)
  private readonly customFieldsService = inject(CustomFieldsService)
  private readonly documentTypeService = inject(DocumentTypeService)
  private readonly documentService = inject(DocumentService)
  private readonly toastService = inject(ToastService)
  private readonly destroy$ = new Subject<void>()

  @ViewChild('zoneCanvas') canvasRef: ElementRef<HTMLCanvasElement>
  @ViewChild('pageImage') imageRef: ElementRef<HTMLImageElement>

  template: OcrTemplate = {
    id: null,
    name: '',
    document_type: null,
    sample_document: null,
    default_page: 0,
    source_width: 0,
    source_height: 0,
    enabled: true,
    zones: [],
  }

  customFields: CustomField[] = []
  documentTypes: any[] = []
  transformOptions = TRANSFORM_OPTIONS
  isNew = true
  saving = false

  // Preview state
  previewDocId: number | null = null
  previewPage = 0
  previewPageCount: number | null = null
  private pageCountForDoc: number | null = null
  pageImageUrl: string | null = null
  imageLoaded = false

  // Tabs: 'settings' | 'zones' | 'zone'
  activeTab: string = 'settings'

  // Drawing state
  isDrawing = false
  currentRect: DrawingRect | null = null
  selectedZoneIndex: number | null = null

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

  // Resize state
  isResizing = false
  resizeHandle: string | null = null // 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'
  resizeZoneIndex: number | null = null
  private readonly HANDLE_SIZE = 8

  // Test results
  testResults: any[] | null = null
  testing = false

  // Per-zone test (in the Zone tab)
  zoneTestResult: any | null = null
  zoneTesting = false

  // Quick create field
  showQuickCreate = false
  quickCreateName = ''
  quickCreateType = 'string'
  quickCreateForZoneIndex: number | null = null
  quickCreateTypes = [
    { id: 'string', name: $localize`String` },
    { id: 'integer', name: $localize`Integer` },
    { id: 'float', name: $localize`Float` },
    { id: 'date', name: $localize`Date` },
    { id: 'monetary', name: $localize`Monetary` },
    { id: 'boolean', name: $localize`Boolean` },
    { id: 'url', name: $localize`URL` },
    { id: 'longtext', name: $localize`Long Text` },
  ]

  ngOnInit() {
    // Load custom fields and document types
    this.customFieldsService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.customFields = r.results))

    this.documentTypeService
      .listAll()
      .pipe(takeUntil(this.destroy$))
      .subscribe((r) => (this.documentTypes = r.results))

    // Load existing template or set up new
    const id = this.route.snapshot.paramMap.get('id')
    if (id && id !== 'new') {
      this.isNew = false
      this.templateService
        .get(parseInt(id))
        .pipe(takeUntil(this.destroy$))
        .subscribe((t) => {
          this.template = t
          if (t.sample_document) {
            this.previewDocId = t.sample_document
            this.loadPreview()
          }
        })
    } else {
      // Pre-fill from query params (e.g. "Create OCR Template" from document detail)
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

  ngAfterViewInit() {}

  loadPreview() {
    if (!this.previewDocId) return
    // Fetch the page count once per document, for the page navigation.
    if (this.pageCountForDoc !== this.previewDocId) {
      this.pageCountForDoc = this.previewDocId
      this.previewPageCount = null
      this.documentService
        .get(this.previewDocId)
        .pipe(takeUntil(this.destroy$))
        .subscribe({
          next: (doc) => (this.previewPageCount = doc?.page_count ?? null),
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

  /** The page a zone belongs to (falls back to the template default). */
  zonePage(zone: OcrTemplateZone): number {
    return zone.page ?? this.template.default_page ?? 0
  }

  private isOnCurrentPage(zone: OcrTemplateZone): boolean {
    return this.zonePage(zone) === this.previewPage
  }

  onImageLoad() {
    this.imageLoaded = true
    const img = this.imageRef.nativeElement
    this.template.source_width = img.naturalWidth
    this.template.source_height = img.naturalHeight
    // The canvas is rendered by @if(imageLoaded) — which only exists after the
    // next change-detection pass — so defer the draw, otherwise the zones don't
    // appear until the user interacts with the preview.
    setTimeout(() => this.redrawCanvas())
  }

  // --- Canvas drawing ---

  onCanvasMouseDown(event: MouseEvent) {
    const rect = this.canvasRef.nativeElement.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // Check if clicking on a resize handle of the selected zone
    if (this.selectedZoneIndex !== null) {
      const handle = this.findHandleAt(x, y, this.selectedZoneIndex)
      if (handle) {
        this.isResizing = true
        this.resizeHandle = handle
        this.resizeZoneIndex = this.selectedZoneIndex
        return
      }
    }

    // Check if clicking on an existing zone — select it and jump to its detail
    const clickedIdx = this.findZoneAt(x, y)
    if (clickedIdx !== null && !event.shiftKey) {
      this.selectZone(clickedIdx)
      return
    }

    // Start drawing new zone (shift+click or click on empty area)
    this.isDrawing = true
    this.currentRect = { startX: x, startY: y, endX: x, endY: y }
    this.selectedZoneIndex = null
  }

  onCanvasMouseMove(event: MouseEvent) {
    const rect = this.canvasRef.nativeElement.getBoundingClientRect()
    const mx = event.clientX - rect.left
    const my = event.clientY - rect.top

    if (this.isResizing && this.resizeZoneIndex !== null && this.resizeHandle) {
      this.applyResize(mx, my)
      this.redrawCanvas()
      return
    }

    if (this.isDrawing && this.currentRect) {
      this.currentRect.endX = mx
      this.currentRect.endY = my
      this.redrawCanvas()
      return
    }

    // Update cursor based on handle proximity
    if (this.selectedZoneIndex !== null) {
      const handle = this.findHandleAt(mx, my, this.selectedZoneIndex)
      const canvas = this.canvasRef.nativeElement
      if (handle) {
        const cursorMap: Record<string, string> = {
          nw: 'nw-resize', ne: 'ne-resize', sw: 'sw-resize', se: 'se-resize',
          n: 'n-resize', s: 's-resize', w: 'w-resize', e: 'e-resize',
        }
        canvas.style.cursor = cursorMap[handle] || 'crosshair'
      } else {
        canvas.style.cursor = 'crosshair'
      }
    }
  }

  onCanvasMouseUp(event: MouseEvent) {
    if (this.isResizing) {
      this.isResizing = false
      this.resizeHandle = null
      this.resizeZoneIndex = null
      return
    }

    if (!this.isDrawing || !this.currentRect) return
    this.isDrawing = false

    const canvas = this.canvasRef.nativeElement
    const img = this.imageRef.nativeElement

    // Scale from display coordinates to image coordinates
    const scaleX = img.naturalWidth / canvas.width
    const scaleY = img.naturalHeight / canvas.height

    const x = Math.round(
      Math.min(this.currentRect.startX, this.currentRect.endX) * scaleX
    )
    const y = Math.round(
      Math.min(this.currentRect.startY, this.currentRect.endY) * scaleY
    )
    const w = Math.round(
      Math.abs(this.currentRect.endX - this.currentRect.startX) * scaleX
    )
    const h = Math.round(
      Math.abs(this.currentRect.endY - this.currentRect.startY) * scaleY
    )

    // Ignore tiny accidental clicks
    if (w < 10 || h < 10) {
      this.currentRect = null
      this.redrawCanvas()
      return
    }

    const zone: OcrTemplateZone = {
      name: `Zone ${this.template.zones.length + 1}`,
      custom_field: this.customFields.length > 0 ? this.customFields[0].id : null,
      x,
      y,
      width: w,
      height: h,
      page: this.previewPage,
      ocr_language: 'deu+eng',
      transform: 'strip',
      validation_regex: '',
      order: this.template.zones.length,
      zone_source_width: img.naturalWidth,
      zone_source_height: img.naturalHeight,
    }

    this.template.zones.push(zone)
    this.currentRect = null
    // Newly drawn zone → select it and open its detail tab.
    this.selectZone(this.template.zones.length - 1)
  }

  private getZoneDisplayRect(zoneIdx: number): { x: number; y: number; w: number; h: number } | null {
    const canvas = this.canvasRef?.nativeElement
    const img = this.imageRef?.nativeElement
    if (!canvas || !img || !img.naturalWidth) return null
    const zone = this.template.zones[zoneIdx]
    if (!zone) return null
    if (!this.isOnCurrentPage(zone)) return null
    const srcW = zone.zone_source_width || img.naturalWidth
    const srcH = zone.zone_source_height || img.naturalHeight
    const scaleX = canvas.width / srcW
    const scaleY = canvas.height / srcH
    return {
      x: zone.x * scaleX,
      y: zone.y * scaleY,
      w: zone.width * scaleX,
      h: zone.height * scaleY,
    }
  }

  private findHandleAt(mx: number, my: number, zoneIdx: number): string | null {
    const r = this.getZoneDisplayRect(zoneIdx)
    if (!r) return null
    const hs = this.HANDLE_SIZE
    const handles: [string, number, number][] = [
      ['nw', r.x, r.y], ['n', r.x + r.w / 2, r.y], ['ne', r.x + r.w, r.y],
      ['w', r.x, r.y + r.h / 2], ['e', r.x + r.w, r.y + r.h / 2],
      ['sw', r.x, r.y + r.h], ['s', r.x + r.w / 2, r.y + r.h], ['se', r.x + r.w, r.y + r.h],
    ]
    for (const [name, hx, hy] of handles) {
      if (Math.abs(mx - hx) <= hs && Math.abs(my - hy) <= hs) return name
    }
    return null
  }

  private applyResize(mx: number, my: number) {
    const canvas = this.canvasRef.nativeElement
    const img = this.imageRef.nativeElement
    const zone = this.template.zones[this.resizeZoneIndex]
    if (!zone) return
    const srcW = zone.zone_source_width || img.naturalWidth
    const srcH = zone.zone_source_height || img.naturalHeight
    const scaleX = srcW / canvas.width
    const scaleY = srcH / canvas.height
    const imgX = Math.round(mx * scaleX)
    const imgY = Math.round(my * scaleY)
    const handle = this.resizeHandle

    if (handle.includes('w')) {
      const right = zone.x + zone.width
      zone.x = Math.max(0, Math.min(imgX, right - 10))
      zone.width = right - zone.x
    }
    if (handle.includes('e')) {
      zone.width = Math.max(10, imgX - zone.x)
    }
    if (handle.includes('n')) {
      const bottom = zone.y + zone.height
      zone.y = Math.max(0, Math.min(imgY, bottom - 10))
      zone.height = bottom - zone.y
    }
    if (handle.includes('s')) {
      zone.height = Math.max(10, imgY - zone.y)
    }
  }

  private findZoneAt(displayX: number, displayY: number): number | null {
    const canvas = this.canvasRef.nativeElement
    const img = this.imageRef.nativeElement
    if (!img.naturalWidth) return null

    for (let i = this.template.zones.length - 1; i >= 0; i--) {
      const z = this.template.zones[i]
      if (!this.isOnCurrentPage(z)) continue
      // Use per-zone source dimensions if available, otherwise current image
      const srcW = z.zone_source_width || img.naturalWidth
      const srcH = z.zone_source_height || img.naturalHeight
      const scaleX = canvas.width / srcW
      const scaleY = canvas.height / srcH
      const zx = z.x * scaleX
      const zy = z.y * scaleY
      const zw = z.width * scaleX
      const zh = z.height * scaleY
      if (
        displayX >= zx &&
        displayX <= zx + zw &&
        displayY >= zy &&
        displayY <= zy + zh
      ) {
        return i
      }
    }
    return null
  }

  redrawCanvas() {
    if (!this.canvasRef || !this.imageRef) return
    const canvas = this.canvasRef.nativeElement
    const img = this.imageRef.nativeElement
    const ctx = canvas.getContext('2d')

    // Match canvas to displayed image size
    canvas.width = img.clientWidth
    canvas.height = img.clientHeight

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw existing zones
    const colors = [
      '#4f8ff7',
      '#ff6b6b',
      '#51cf66',
      '#ffd43b',
      '#cc5de8',
      '#ff922b',
      '#20c997',
      '#e599f7',
    ]

    this.template.zones.forEach((zone, idx) => {
      // Only draw zones that belong to the page currently shown.
      if (!this.isOnCurrentPage(zone)) return
      const color = colors[idx % colors.length]
      // Use per-zone source dimensions for correct scaling
      const srcW = zone.zone_source_width || img.naturalWidth
      const srcH = zone.zone_source_height || img.naturalHeight
      const scaleX = canvas.width / srcW
      const scaleY = canvas.height / srcH
      const x = zone.x * scaleX
      const y = zone.y * scaleY
      const w = zone.width * scaleX
      const h = zone.height * scaleY

      ctx.strokeStyle = color
      ctx.lineWidth = idx === this.selectedZoneIndex ? 3 : 2
      ctx.strokeRect(x, y, w, h)

      ctx.fillStyle = color + '20'
      ctx.fillRect(x, y, w, h)

      // Label
      ctx.fillStyle = color
      ctx.font = '12px sans-serif'
      ctx.fillText(zone.name, x + 4, y + 14)

      // Draw resize handles on selected zone
      if (idx === this.selectedZoneIndex) {
        const hs = this.HANDLE_SIZE
        ctx.fillStyle = color
        const handles = [
          [x, y], [x + w / 2, y], [x + w, y],
          [x, y + h / 2], [x + w, y + h / 2],
          [x, y + h], [x + w / 2, y + h], [x + w, y + h],
        ]
        for (const [hx, hy] of handles) {
          ctx.fillRect(hx - hs / 2, hy - hs / 2, hs, hs)
        }
      }
    })

    // Draw current selection rect
    if (this.currentRect) {
      ctx.strokeStyle = '#ffffff'
      ctx.lineWidth = 2
      ctx.setLineDash([5, 5])
      ctx.strokeRect(
        this.currentRect.startX,
        this.currentRect.startY,
        this.currentRect.endX - this.currentRect.startX,
        this.currentRect.endY - this.currentRect.startY
      )
      ctx.setLineDash([])
    }
  }

  removeZone(index: number) {
    this.template.zones.splice(index, 1)
    if (this.selectedZoneIndex === index) {
      this.selectedZoneIndex = null
    } else if (this.selectedZoneIndex > index) {
      this.selectedZoneIndex--
    }
    this.redrawCanvas()
  }

  selectZone(index: number) {
    this.selectedZoneIndex = index
    this.activeTab = 'zone'
    this.zoneTestResult = null
    // Jump the preview to the zone's page so it's actually visible.
    const zone = this.template.zones[index]
    if (zone) this.goToPage(this.zonePage(zone))
    this.redrawCanvas()
  }

  testZone() {
    const zone = this.selectedZone
    if (!zone || !this.previewDocId) return
    this.zoneTesting = true
    this.zoneTestResult = null
    this.templateService
      .testZone(this.previewDocId, {
        name: zone.name,
        x: zone.x,
        y: zone.y,
        width: zone.width,
        height: zone.height,
        page: zone.page ?? this.template.default_page,
        ocr_language: zone.ocr_language,
        transform: zone.transform,
        validation_regex: zone.validation_regex,
        zone_source_width: zone.zone_source_width,
        zone_source_height: zone.zone_source_height,
      })
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.zoneTestResult = res
          this.zoneTesting = false
        },
        error: (err) => {
          this.zoneTestResult = { error: err.error?.error || $localize`Test failed` }
          this.zoneTesting = false
        },
      })
  }

  deleteSelectedZone() {
    if (this.selectedZoneIndex === null) return
    this.removeZone(this.selectedZoneIndex)
    this.activeTab = 'zones'
  }

  // --- Save / Test ---

  save() {
    this.saving = true
    this.template.sample_document = this.previewDocId
    const obs = this.isNew
      ? this.templateService.create(this.template)
      : this.templateService.update(this.template)

    obs.pipe(takeUntil(this.destroy$)).subscribe({
      next: (saved) => {
        // Keep the editor open so the user can keep tuning zones without having
        // to reopen the template after every save.
        const idx = this.selectedZoneIndex
        this.template = saved
        this.isNew = false
        this.selectedZoneIndex = idx
        this.saving = false
        this.toastService.showInfo($localize`OCR template saved.`)
        this.redrawCanvas()
      },
      error: (e) => {
        this.saving = false
        this.toastService.showError($localize`Error saving OCR template.`, e)
      },
    })
  }

  testOnDocument() {
    if (!this.template.id || !this.previewDocId) return
    this.testing = true
    this.testResults = null
    this.templateService
      .testExtraction(this.template.id, this.previewDocId)
      .pipe(takeUntil(this.destroy$))
      .subscribe({
        next: (res) => {
          this.testResults = res.results
          this.testing = false
        },
        error: () => {
          this.testing = false
        },
      })
  }

  getCustomFieldName(id: number): string {
    const cf = this.customFields.find((f) => f.id === id)
    return cf ? cf.name : `Field #${id}`
  }

  getDocumentTypeName(id: number): string {
    const dt = this.documentTypes.find((d) => d.id === id)
    return dt ? dt.name : `Type #${id}`
  }

  openQuickCreate(zoneIndex: number | null) {
    if (zoneIndex === null) return
    this.quickCreateForZoneIndex = zoneIndex
    this.quickCreateName = this.template.zones[zoneIndex]?.name || ''
    this.quickCreateType = 'string'
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
          // Clear cache and refresh custom fields list
          this.customFieldsService.clearCache()
          this.customFieldsService
            .listAll()
            .pipe(takeUntil(this.destroy$))
            .subscribe((r) => {
              this.customFields = r.results
              // Assign the new field to the zone
              if (this.quickCreateForZoneIndex !== null) {
                this.template.zones[this.quickCreateForZoneIndex].custom_field = result.id
              }
              this.showQuickCreate = false
              this.quickCreateForZoneIndex = null
            })
        },
        error: (err) => {
          alert(err.error?.error || 'Failed to create custom field')
        },
      })
  }

  ngOnDestroy() {
    this.destroy$.next()
    this.destroy$.complete()
  }
}
