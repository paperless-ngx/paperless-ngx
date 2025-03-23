import { CommonModule } from '@angular/common'
import { Component, Input } from '@angular/core'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { MarkdownModule } from 'ngx-markdown'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'

@Component({
  selector: 'pngx-markdown-modal',
  templateUrl: './markdown-modal.component.html',
  styleUrls: ['./markdown-modal.component.scss'],
  standalone: true,
  imports: [
    CommonModule,
    MarkdownModule,
    NgxBootstrapIconsModule,
  ],
})
export class MarkdownModalComponent {
  @Input() content: string
  @Input() title: string
  @Input() isRTL: boolean

  constructor(public activeModal: NgbActiveModal) { }
}
