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
import { PaperlessDocument } from 'src/app/data/paperless-document'
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
  foundDocuments$: Observable<PaperlessDocument[]>
  loading = false
  selectedDocuments: PaperlessDocument[] = []

  private unsubscribeNotifier: Subject<any> = new Subject()

  @Input()
  notFoundText: string = $localize`No documents found`

  constructor(private documentsService: DocumentService) {
    super()
  }

  ngOnInit() {
    this.loadDocs()
  }

  writeValue(documentIDs: number[]): void {
    this.loading = true
    this.documentsService
      .getCachedMany(documentIDs)
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((documents) => {
        this.loading = false
        this.selectedDocuments = documents
        super.writeValue(documentIDs)
      })
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
              map((results) => results.results),
              catchError(() => of([])), // empty on error
              tap(() => (this.loading = false))
            )
        )
      )
    )
  }

  unselect(document: PaperlessDocument): void {
    this.selectedDocuments = this.selectedDocuments.filter(
      (d) => d.id !== document.id
    )
    this.onChange(this.selectedDocuments.map((d) => d.id))
  }

  compareDocuments(
    document: PaperlessDocument,
    selectedDocument: PaperlessDocument
  ) {
    return document.id === selectedDocument.id
  }

  trackByFn(item: PaperlessDocument) {
    return item.id
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }
}
