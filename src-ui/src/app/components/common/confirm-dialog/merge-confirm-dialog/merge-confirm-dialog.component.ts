import { Component, OnInit } from '@angular/core'
import { ConfirmDialogComponent } from '../confirm-dialog.component'
import { NgbActiveModal } from '@ng-bootstrap/ng-bootstrap'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PermissionsService } from 'src/app/services/permissions.service'
import { CdkDragDrop, moveItemInArray } from '@angular/cdk/drag-drop'
import { Subject, takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'

@Component({
  selector: 'pngx-merge-confirm-dialog',
  templateUrl: './merge-confirm-dialog.component.html',
  styleUrl: './merge-confirm-dialog.component.scss',
})
export class MergeConfirmDialogComponent
  extends ConfirmDialogComponent
  implements OnInit
{
  public documentIDs: number[] = []
  public deleteOriginals: boolean = false
  private _documents: Document[] = []
  get documents(): Document[] {
    return this._documents
  }

  public metadataDocumentID: number = -1

  private unsubscribeNotifier: Subject<any> = new Subject()

  constructor(
    activeModal: NgbActiveModal,
    private documentService: DocumentService,
    private permissionService: PermissionsService
  ) {
    super(activeModal)
  }

  ngOnInit() {
    this.documentService
      .getFew(this.documentIDs)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this._documents = r.results
      })
  }

  onDrop(event: CdkDragDrop<number[]>) {
    moveItemInArray(this.documentIDs, event.previousIndex, event.currentIndex)
  }

  getDocument(documentID: number): Document {
    return this.documents.find((d) => d.id === documentID)
  }

  get userOwnsAllDocuments(): boolean {
    return this.documents.every((d) =>
      this.permissionService.currentUserOwnsObject(d)
    )
  }
}
