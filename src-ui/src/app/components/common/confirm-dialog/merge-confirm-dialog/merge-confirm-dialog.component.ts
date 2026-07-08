import {
  CdkDragDrop,
  DragDropModule,
  moveItemInArray,
} from '@angular/cdk/drag-drop'
import { AsyncPipe } from '@angular/common'
import { Component, OnInit, inject, signal } from '@angular/core'
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

  private documentIDsSignal = signal<number[]>([])
  private archiveFallbackSignal = signal(false)
  private deleteOriginalsSignal = signal(false)
  private documentsSignal = signal<Document[]>([])
  private metadataDocumentIDSignal = signal(-1)

  public get documentIDs(): number[] {
    return this.documentIDsSignal()
  }

  public set documentIDs(documentIDs: number[]) {
    this.documentIDsSignal.set(documentIDs)
  }

  public get archiveFallback(): boolean {
    return this.archiveFallbackSignal()
  }

  public set archiveFallback(archiveFallback: boolean) {
    this.archiveFallbackSignal.set(archiveFallback)
  }

  public get deleteOriginals(): boolean {
    return this.deleteOriginalsSignal()
  }

  public set deleteOriginals(deleteOriginals: boolean) {
    this.deleteOriginalsSignal.set(deleteOriginals)
  }

  get documents(): Document[] {
    return this.documentsSignal()
  }

  public get metadataDocumentID(): number {
    return this.metadataDocumentIDSignal()
  }

  public set metadataDocumentID(metadataDocumentID: number) {
    this.metadataDocumentIDSignal.set(metadataDocumentID)
  }

  constructor() {
    super()
  }

  ngOnInit() {
    this.documentService
      .getFew(this.documentIDs)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((r) => {
        this.documentsSignal.set(r.results)
      })
  }

  onDrop(event: CdkDragDrop<number[]>) {
    const documentIDs = this.documentIDs.concat()
    moveItemInArray(documentIDs, event.previousIndex, event.currentIndex)
    this.documentIDs = documentIDs
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
