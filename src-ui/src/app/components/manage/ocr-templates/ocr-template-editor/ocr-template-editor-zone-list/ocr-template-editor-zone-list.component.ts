import { Component, EventEmitter, Input, Output } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CustomField } from 'src/app/data/custom-field'
import { OCR_BUILTIN_TARGETS, OcrTemplateZone } from 'src/app/data/ocr-template'
import { getZonePage } from '../zone-geometry'

@Component({
  selector: 'pngx-ocr-template-zone-list',
  imports: [NgxBootstrapIconsModule],
  templateUrl: './ocr-template-editor-zone-list.component.html',
})
export class OcrTemplateEditorZoneListComponent {
  @Input() zones: OcrTemplateZone[] = []
  @Input() selectedZoneIndex: number | null = null
  @Input() previewPage = 0
  @Input() previewPageCount: number | null = null
  @Input() customFields: CustomField[] = []

  @Output() zoneSelected = new EventEmitter<number>()
  @Output() zoneRemoved = new EventEmitter<number>()

  zonePage(zone: OcrTemplateZone): number {
    return getZonePage(zone, this.previewPage, this.previewPageCount)
  }

  getZoneTargetName(zone: OcrTemplateZone): string {
    const target = zone.target || 'custom_field'
    if (target === 'custom_field') {
      return zone.custom_field
        ? this.getCustomFieldName(zone.custom_field)
        : $localize`(no field)`
    }
    return OCR_BUILTIN_TARGETS.find((t) => t.id === target)?.name ?? target
  }

  private getCustomFieldName(id: number): string {
    return (
      this.customFields.find((field) => field.id === id)?.name ?? `Field #${id}`
    )
  }
}
