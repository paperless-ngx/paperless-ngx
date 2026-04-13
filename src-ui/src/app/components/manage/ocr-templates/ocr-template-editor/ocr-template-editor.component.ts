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

interface DrawingRect {
  startX: number
  startY: number
  endX: number
  endY: number
}

@Component({
  selector: 'pngx-ocr-template-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, NgxBootstrapIconsModule],
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
  pageImageUrl: string | null = null
  imageLoaded = false

  // Drawing state
  isDrawing = false
  currentRect: DrawingRect | null = null
  selectedZoneIndex: number | null = null

  // Test results
  testResults: any[] | null = null
  testing = false

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
    }
  }

  ngAfterViewInit() {}

  loadPreview() {
    if (!this.previewDocId) return
    this.pageImageUrl = this.templateService.getPageImageUrl(
      this.previewDocId,
      this.previewPage
    )
    this.imageLoaded = false
  }

  onImageLoad() {
    this.imageLoaded = true
    const img = this.imageRef.nativeElement
    this.template.source_width = img.naturalWidth
    this.template.source_height = img.naturalHeight
    this.redrawCanvas()
  }

  // --- Canvas drawing ---

  onCanvasMouseDown(event: MouseEvent) {
    const rect = this.canvasRef.nativeElement.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top

    // Check if clicking on an existing zone
    const clickedIdx = this.findZoneAt(x, y)
    if (clickedIdx !== null && !event.shiftKey) {
      this.selectedZoneIndex = clickedIdx
      this.redrawCanvas()
      return
    }

    // Start drawing new zone (shift+click or click on empty area)
    this.isDrawing = true
    this.currentRect = { startX: x, startY: y, endX: x, endY: y }
    this.selectedZoneIndex = null
  }

  onCanvasMouseMove(event: MouseEvent) {
    if (!this.isDrawing || !this.currentRect) return
    const rect = this.canvasRef.nativeElement.getBoundingClientRect()
    this.currentRect.endX = event.clientX - rect.left
    this.currentRect.endY = event.clientY - rect.top
    this.redrawCanvas()
  }

  onCanvasMouseUp(event: MouseEvent) {
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
      ocr_language: 'deu+eng',
      transform: 'strip',
      order: this.template.zones.length,
      // Store per-zone source dimensions from the current page image
      // Handles mixed page sizes in PDFs (landscape/portrait, different formats)
      zone_source_width: img.naturalWidth,
      zone_source_height: img.naturalHeight,
    }

    this.template.zones.push(zone)
    this.selectedZoneIndex = this.template.zones.length - 1
    this.currentRect = null
    this.redrawCanvas()
  }

  private findZoneAt(displayX: number, displayY: number): number | null {
    const canvas = this.canvasRef.nativeElement
    const img = this.imageRef.nativeElement
    if (!img.naturalWidth) return null

    for (let i = this.template.zones.length - 1; i >= 0; i--) {
      const z = this.template.zones[i]
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
    this.redrawCanvas()
  }

  // --- Save / Test ---

  save() {
    this.saving = true
    this.template.sample_document = this.previewDocId
    const obs = this.isNew
      ? this.templateService.create(this.template)
      : this.templateService.update(this.template)

    obs.pipe(takeUntil(this.destroy$)).subscribe({
      next: () => {
        this.saving = false
        this.router.navigate(['/ocr-templates'])
      },
      error: () => {
        this.saving = false
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

  openQuickCreate(zoneIndex: number) {
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
          // Refresh custom fields list
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
