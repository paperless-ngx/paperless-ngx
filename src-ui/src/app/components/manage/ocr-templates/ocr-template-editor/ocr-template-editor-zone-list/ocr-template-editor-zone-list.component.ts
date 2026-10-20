import { Component, EventEmitter, Input, Output } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { CustomField } from 'src/app/data/custom-field'
import {
  getZoneFieldKey,
  OCR_BUILTIN_TARGETS,
  OcrTemplateZone,
  OcrZoneTarget,
} from 'src/app/data/ocr-template'
import { getZoneColor } from '../zone-geometry'

@Component({
  selector: 'pngx-ocr-template-zone-list',
  imports: [NgxBootstrapIconsModule],
  templateUrl: './ocr-template-editor-zone-list.component.html',
})
export class OcrTemplateEditorZoneListComponent {
  @Input() zones: OcrTemplateZone[] = []
  @Input() customFields: CustomField[] = []

  @Output() zoneSelected = new EventEmitter<number>()
  @Output() zoneRemoved = new EventEmitter<number>()

  readonly zoneColor = getZoneColor

  hasField(zone: OcrTemplateZone): boolean {
    return getZoneFieldKey(zone) !== null
  }

  isCombined(zone: OcrTemplateZone): boolean {
    const key = getZoneFieldKey(zone)
    return (
      key !== null &&
      this.zones.filter((z) => getZoneFieldKey(z) === key).length > 1
    )
  }

  getZoneTargetName(zone: OcrTemplateZone): string {
    if (zone.target === OcrZoneTarget.CustomField) {
      return (
        this.customFields.find((field) => field.id === zone.custom_field)
          ?.name ?? ''
      )
    }
    return (
      OCR_BUILTIN_TARGETS.find((target) => target.id === zone.target)?.name ??
      ''
    )
  }
}
