import { Component, EventEmitter, Input, Output, inject } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentLinkComponent } from 'src/app/components/common/input/document-link/document-link.component'

@Component({
  selector: 'pngx-add-existing-document-version-dialog',
  templateUrl: './add-existing-document-version-dialog.component.html',
  imports: [DocumentLinkComponent, FormsModule],
})
export class AddExistingDocumentVersionDialogComponent {
  private readonly activeModal = inject(NgbActiveModal)

  @Input() rootDocumentID: number
  @Output() confirmClicked = new EventEmitter<number>()

  selectedDocumentIDs: number[] = []
  buttonsEnabled = true

  confirm(): void {
    if (this.selectedDocumentIDs.length !== 1) return
    this.confirmClicked.emit(this.selectedDocumentIDs[0])
  }

  cancel(): void {
    this.activeModal.dismiss()
  }
}
