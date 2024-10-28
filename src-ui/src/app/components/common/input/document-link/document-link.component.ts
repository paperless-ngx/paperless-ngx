import { Component, forwardRef, OnInit, Input, OnDestroy } from '@angular/core'
import { NG_VALUE_ACCESSOR } from '@angular/forms'
import {
  Subject,
  Observable,
  takeUntil,
  concat,
  of,
  distinctUntilChanged,
  tap,
  switchMap,
  map,
  catchError,
} from 'rxjs'
import { FILTER_TITLE } from 'src/app/data/filter-rule-type'
import { Document } from 'src/app/data/document'
import { DocumentService } from 'src/app/services/rest/document.service'
import { AbstractInputComponent } from '../abstract-input'

@Component({
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DocumentLinkComponent),
      multi: true,
    },
  ],
  selector: 'pngx-input-document-link',
  templateUrl: './document-link.component.html',
  styleUrls: ['./document-link.component.scss'],
})
export class DocumentLinkComponent
  extends AbstractInputComponent<any[]>
  implements OnInit, OnDestroy
{
  documentsInput$ = new Subject<string>()
  foundDocuments$: Observable<Document[]>
  loading = false
  selectedDocuments: Document[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()

  @Input()
  notFoundText: string = $localize`No documents found`

  @Input()
  parentDocumentID: number

  @Input()
  minimal: boolean = false

  @Input()
  placeholder: string = $localize`Search for documents`

  constructor(private documentsService: DocumentService) {
    super()
  }

  ngOnInit() {
    this.loadDocs()
  }

  writeValue(documentIDs: number[]): void {
    if (!documentIDs || documentIDs.length === 0) {
      this.selectedDocuments = []
      super.writeValue([])
    } else {
      this.loading = true
      this.documentsService
        .getFew(documentIDs, { fields: 'id,title' })
        .pipe(takeUntil(this.unsubscribeNotifier))
        .subscribe((documentResults) => {
          this.loading = false
          this.selectedDocuments = documentIDs.map((id) =>
            documentResults.results.find((d) => d.id === id)
          )
          super.writeValue(documentIDs)
        })
    }
  }

  private loadDocs() {
    this.foundDocuments$ = concat(
      of([]), // default items
      this.documentsInput$.pipe(
        distinctUntilChanged(),
        takeUntil(this.unsubscribeNotifier),
        tap(() => (this.loading = true)),
        switchMap((title) =>
          this.documentsService
            .listFiltered(
              1,
              null,
              'created',
              true,
              [{ rule_type: FILTER_TITLE, value: title }],
              { truncate_content: true }
            )
            .pipe(
              map((results) =>
                results.results.filter(
                  (d) =>
                    d.id !== this.parentDocumentID &&
                    !this.selectedDocuments.find((sd) => sd.id === d.id)
                )
              ),
              catchError(() => of([])), // empty on error
              tap(() => (this.loading = false))
            )
        )
      )
    )
  }

  unselect(document: Document): void {
    this.selectedDocuments = this.selectedDocuments.filter(
      (d) => d && d.id !== document.id
    )
    this.onChange(this.selectedDocuments.map((d) => d.id))
  }

  compareDocuments(document: Document, selectedDocument: Document) {
    return document.id === selectedDocument.id
  }

  trackByFn(item: Document) {
    return item.id
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }
}
