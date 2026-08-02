import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { AsyncPipe } from '@angular/common'
import {
  Component,
  Input,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { NgxBootstrapIconsModule } from 'ngx-bootstrap-icons'
import { takeUntil } from 'rxjs'
import { Document } from 'src/app/data/document'
import { CorrespondentNamePipe } from 'src/app/pipes/correspondent-name.pipe'
import { CustomDatePipe } from 'src/app/pipes/custom-date.pipe'
import { PermissionsService } from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { ConfirmDialogComponent } from '../confirm-dialog.component'

@Component({
  selector: 'pngx-merge-confirm-dialog',
  templateUrl: './merge-confirm-dialog.component.html',
  styleUrl: './merge-confirm-dialog.component.scss',
  imports: [
    AsyncPipe,
    CorrespondentNamePipe,
    CustomDatePipe,
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

  readonly documentIDs = signal<number[]>([])
  readonly archiveFallback = signal(false)
  readonly deleteOriginals = signal(false)
  readonly documents = signal<Document[]>([])
  readonly metadataDocumentID = signal(-1)
  readonly rootDocumentID = signal(-1)
  readonly draggableDocumentIDs = computed(() =>
    this.documentIDs().filter(
      (documentID) => documentID !== this.rootDocumentID()
    )
  )

  @Input()
  mergeAsVersions = false

  constructor() {
    super()
  }

  ngOnInit() {
    this.documentService
      .getFew(this.documentIDs())
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.documents.set(r.results)
      })
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
    return this.documents().find((d) => d.id === documentID)
  }

  get userOwnsAllDocuments(): boolean {
    return this.documents().every((d) =>
      this.permissionService.currentUserOwnsObject(d)
    )
  }
}
