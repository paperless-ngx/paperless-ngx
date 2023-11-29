import {
  Component,
  Input,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
} from '@angular/core'
import { Params, Router } from '@angular/router'
import { Subject, takeUntil } from 'rxjs'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { PaperlessSavedView } from 'src/app/data/paperless-saved-view'
import { ConsumerStatusService } from 'src/app/services/consumer-status.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import {
  FILTER_CORRESPONDENT,
  FILTER_HAS_TAGS_ALL,
} from 'src/app/data/filter-rule-type'
import { OpenDocumentsService } from 'src/app/services/open-documents.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { ComponentWithPermissions } from 'src/app/components/with-permissions/with-permissions.component'
import { NgbPopover } from '@ng-bootstrap/ng-bootstrap'
import { queryParamsFromFilterRules } from 'src/app/utils/query-params'

@Component({
  selector: 'pngx-saved-view-widget',
  templateUrl: './saved-view-widget.component.html',
  styleUrls: [
    './saved-view-widget.component.scss',
    '../../../document-list/popover-preview/popover-preview.scss',
  ],
})
export class SavedViewWidgetComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy
{
  loading: boolean = true

  constructor(
    private documentService: DocumentService,
    private router: Router,
    private list: DocumentListViewService,
    private consumerStatusService: ConsumerStatusService,
    public openDocumentsService: OpenDocumentsService,
    public documentListViewService: DocumentListViewService
  ) {
    super()
  }

  @Input()
  savedView: PaperlessSavedView

  documents: PaperlessDocument[] = []

  unsubscribeNotifier: Subject<any> = new Subject()

  @ViewChildren('popover') popovers: QueryList<NgbPopover>
  popover: NgbPopover

  mouseOnPreview = false
  popoverHidden = true

  ngOnInit(): void {
    this.reload()
    this.consumerStatusService
      .onDocumentConsumptionFinished()
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe(() => {
        this.reload()
      })
  }

  ngOnDestroy(): void {
    this.unsubscribeNotifier.next(true)
    this.unsubscribeNotifier.complete()
  }

  reload() {
    this.loading = this.documents.length == 0
    this.documentService
      .listFiltered(
        1,
        10,
        this.savedView.sort_field,
        this.savedView.sort_reverse,
        this.savedView.filter_rules,
        { truncate_content: true }
      )
      .pipe(takeUntil(this.unsubscribeNotifier))
      .subscribe((result) => {
        this.loading = false
        this.documents = result.results
      })
  }

  showAll() {
    if (this.savedView.show_in_sidebar) {
      this.router.navigate(['view', this.savedView.id])
    } else {
      this.router.navigate(['documents'], {
        queryParams: { view: this.savedView.id },
      })
    }
  }

  clickTag(tag: PaperlessTag, event: MouseEvent) {
    event.preventDefault()
    event.stopImmediatePropagation()

    this.list.quickFilter([
      { rule_type: FILTER_HAS_TAGS_ALL, value: tag.id.toString() },
    ])
  }

  getPreviewUrl(document: PaperlessDocument): string {
    return this.documentService.getPreviewUrl(document.id)
  }

  getDownloadUrl(document: PaperlessDocument): string {
    return this.documentService.getDownloadUrl(document.id)
  }

  mouseEnterPreview(doc: PaperlessDocument) {
    this.popover = this.popovers.get(this.documents.indexOf(doc))
    this.mouseOnPreview = true
    if (!this.popover.isOpen()) {
      // we're going to open but hide to pre-load content during hover delay
      this.popover.open()
      this.popoverHidden = true
      setTimeout(() => {
        if (this.mouseOnPreview) {
          // show popover
          this.popoverHidden = false
        } else {
          this.popover.close()
        }
      }, 600)
    }
  }

  mouseLeavePreview() {
    this.mouseOnPreview = false
  }

  mouseLeaveCard() {
    this.popover?.close()
  }

  getCorrespondentQueryParams(correspondentId: number): Params {
    return correspondentId !== undefined
      ? queryParamsFromFilterRules([
          {
            rule_type: FILTER_CORRESPONDENT,
            value: correspondentId.toString(),
          },
        ])
      : null
  }
}
