import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { AsyncPipe } from '@angular/common'
import { Component, OnInit, computed, inject, signal } from '@angular/core'
import { FormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-merge-as-versions-confirm-dialog',
  templateUrl: './merge-as-versions-confirm-dialog.component.html',
  styleUrl: './merge-as-versions-confirm-dialog.component.scss',
  imports: [
    AsyncPipe,
    CorrespondentNamePipe,
    CustomDatePipe,
    DragDropModule,
    FormsModule,
    NgxBootstrapIconsModule,
  ],
})
export class MergeAsVersionsConfirmDialogComponent
  extends ConfirmDialogComponent
  implements OnInit
{
  private documentService = inject(DocumentService)

  readonly documentIDs = signal<number[]>([])
  readonly documents = signal<Document[]>([])
  readonly rootDocumentID = signal(-1)
  readonly draggableDocumentIDs = computed(() =>
    this.documentIDs().filter(
      (documentID) => documentID !== this.rootDocumentID()
    )
  )

  ngOnInit() {
    this.documentService
      .getFew(this.documentIDs())
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((response) => this.documents.set(response.results))
  }

  onDrop(event: CdkDragDrop<number[]>) {
    const draggableDocumentIDs = this.draggableDocumentIDs().concat()
    moveItemInArray(
      draggableDocumentIDs,
      event.previousIndex,
      event.currentIndex
    )

    let draggableIndex = 0
    this.documentIDs.update((documentIDs) =>
      documentIDs.map((documentID) =>
        documentID === this.rootDocumentID()
          ? documentID
          : draggableDocumentIDs[draggableIndex++]
      )
    )
  }

  getDocument(documentID: number): Document {
    return this.documents().find((document) => document.id === documentID)
  }
}
