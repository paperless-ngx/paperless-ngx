import { Component, inject } from '@angular/core'
import { Router } from '@angular/router'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { FILTER_MIME_TYPE } from 'src/app/data/filter-rule-type'

interface InputType {
  icon: string
  label: string
  /** Subtitle shown on hover */
  hint: string
  /** mime_type filter value; null = unfiltered / placeholder */
  mime: string | null
  /** Visual color hint (background tint for the card) */
  tone: 'blue' | 'green' | 'orange' | 'red' | 'purple' | 'pink' | 'cyan' | 'yellow'
}

interface PipelineStage {
  icon: string
  label: string
  hint: string
}

@Component({
  selector: 'pngx-pipeline-widget',
  templateUrl: './pipeline-widget.component.html',
  styleUrls: ['./pipeline-widget.component.scss'],
  imports: [NgxBootstrapIconsModule],
})
export class PipelineWidgetComponent {
  private router = inject(Router)
  private documentListViewService = inject(DocumentListViewService)

  readonly inputTypes: InputType[] = [
    { icon: 'file-earmark-pdf', label: $localize`PDF`, hint: $localize`Scanned & digital PDFs`, mime: 'application/pdf', tone: 'red' },
    { icon: 'image', label: $localize`Images`, hint: $localize`JPEG, PNG, TIFF, HEIC`, mime: 'image/jpeg', tone: 'green' },
    { icon: 'file-earmark-word', label: $localize`Office`, hint: $localize`Word, Excel, PowerPoint, ODF`, mime: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', tone: 'blue' },
    { icon: 'envelope', label: $localize`Email`, hint: $localize`.eml with attachments`, mime: 'message/rfc822', tone: 'yellow' },
    { icon: 'camera-video', label: $localize`Video`, hint: $localize`MP4, MOV, MKV`, mime: 'video/mp4', tone: 'purple' },
    { icon: 'mic', label: $localize`Audio`, hint: $localize`MP3, WAV, M4A`, mime: 'audio/mpeg', tone: 'pink' },
    { icon: 'globe', label: $localize`Web`, hint: $localize`HTML, Markdown, Web archives`, mime: 'text/html', tone: 'cyan' },
  ]

  readonly pipelineStages: PipelineStage[] = [
    { icon: 'eye', label: $localize`OCR / VLM`, hint: $localize`Text & content extraction` },
    { icon: 'tag', label: $localize`LLM Tags`, hint: $localize`AI auto-tagging` },
    { icon: 'diagram-3', label: $localize`Classify`, hint: $localize`Correspondent / Type` },
    { icon: 'bullseye', label: $localize`Embed`, hint: $localize`Vector index` },
    { icon: 'lightning-charge', label: $localize`Workflow`, hint: $localize`Triggers & actions` },
  ]

  get supportedFormats(): number {
    return this.inputTypes.length
  }

  openType(type: InputType): void {
    if (!type.mime) return
    this.documentListViewService.quickFilter([
      { rule_type: FILTER_MIME_TYPE, value: type.mime },
    ])
    this.router.navigate(['/documents'])
  }
}