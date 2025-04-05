import { CommonModule } from '@angular/common'
import { Component, Input, OnInit } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { MarkdownModule } from 'ngx-markdown'
import { MarkdownConfigService } from 'src/app/services/markdown-config.service'

@Component({
  selector: 'pngx-markdown-modal',
  templateUrl: './markdown-modal.component.html',
  styleUrls: ['./markdown-modal.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    NgxBootstrapIconsModule,
    MarkdownModule
  ],
})
export class MarkdownModalComponent implements OnInit {
  @Input() content: string
  @Input() title: string
  @Input() isRTL: boolean
  @Input() documentId: number

  constructor(
    public activeModal: NgbActiveModal,
    private markdownConfigService: MarkdownConfigService
  ) { }

  ngOnInit() {
    if (this.documentId) {
      this.markdownConfigService.setCurrentDocumentId(this.documentId)
    }
  }
}
