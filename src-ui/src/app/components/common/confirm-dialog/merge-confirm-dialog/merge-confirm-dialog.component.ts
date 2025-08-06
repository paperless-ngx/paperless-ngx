import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { Component, OnInit, inject } from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-merge-confirm-dialog',
  templateUrl: './merge-confirm-dialog.component.html',
  styleUrl: './merge-confirm-dialog.component.scss',
  imports: [
    DragDropModule,
    FormsModule,
    ReactiveFormsModule,
    NgxBootstrapIconsModule,
  ],
})
export class MergeConfirmDialogComponent
  extends ConfirmDialogComponent
  implements OnInit
{
  private documentService = inject(DocumentService)
  private permissionService = inject(PermissionsService)

  public documentIDs: number[] = []
  public archiveFallback: boolean = false
  public deleteOriginals: boolean = false
  private _documents: Document[] = []
  get documents(): Document[] {
    return this._documents
  }

  public metadataDocumentID: number = -1

  constructor() {
    super()
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
