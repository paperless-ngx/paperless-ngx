import { NgStyle } from '@angular/common'
import { Component, inject, signal } from '@angular/core'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-rotate-confirm-dialog',
  templateUrl: './rotate-confirm-dialog.component.html',
  styleUrl: './rotate-confirm-dialog.component.scss',
  imports: [NgStyle, NgxBootstrapIconsModule],
})
export class RotateConfirmDialogComponent extends ConfirmDialogComponent {
  documentService = inject(DocumentService)

  private documentIDSignal = signal<number>(undefined)
  private showPDFNoteSignal = signal(true)
  private rotationSignal = signal(0)

  public get documentID(): number {
    return this.documentIDSignal()
  }

  public set documentID(documentID: number) {
    this.documentIDSignal.set(documentID)
  }

  public get showPDFNote(): boolean {
    return this.showPDFNoteSignal()
  }

  public set showPDFNote(showPDFNote: boolean) {
    this.showPDFNoteSignal.set(showPDFNote)
  }

  // animation is better if we dont normalize yet
  public get rotation(): number {
    return this.rotationSignal()
  }

  public get degrees(): number {
    let degrees = this.rotation % 360
    if (degrees < 0) degrees += 360
    return degrees
  }

  constructor() {
    super()
  }

  rotate(clockwise: boolean = true) {
    this.rotationSignal.update((rotation) => rotation + (clockwise ? 90 : -90))
  }
}
