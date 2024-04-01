import {
  Component,
  ElementRef,
  HostListener,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { Router } from '@angular/router'
import { NgbDropdown, NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { Subject, debounceTime, distinctUntilChanged, filter } from 'rxjs'
import { ObjectWithId } from 'src/app/data/object-with-id'
import {
  GlobalSearchResult,
  SearchService,
} from 'src/app/services/rest/search.service'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { MailAccountEditDialogComponent } from '../../common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { MailRuleEditDialogComponent } from '../../common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { WorkflowEditDialogComponent } from '../../common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  FILTER_HAS_ANY_TAG,
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_HAS_STORAGE_PATH_ANY,
} from 'src/app/data/filter-rule-type'

@Component({
  selector: 'pngx-global-search',
  templateUrl: './global-search.component.html',
  styleUrl: './global-search.component.scss',
})
export class GlobalSearchComponent {
  public query: string
  public queryDebounce: Subject<string>
  public searchResults: GlobalSearchResult
  private currentItemIndex: number = -1
  public loading: boolean = false

  @ViewChild('searchInput') searchInput: ElementRef
  @ViewChild('resultsDropdown') resultsDropdown: NgbDropdown
  @ViewChildren('resultItem') resultItems: QueryList<ElementRef>
  @ViewChildren('primaryButton') primaryButtons: QueryList<ElementRef>
  @ViewChildren('secondaryButton') secondaryButtons: QueryList<ElementRef>

  @HostListener('document:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    if (event.key === 'k' && (event.ctrlKey || event.metaKey)) {
      this.searchInput.nativeElement.focus()
    }

    if (this.searchResults && this.resultsDropdown.isOpen()) {
      if (event.key === 'ArrowDown') {
        if (this.currentItemIndex < this.searchResults.total - 1) {
          this.currentItemIndex++
          this.setCurrentItem()
          event.preventDefault()
        }
      } else if (event.key === 'ArrowUp') {
        if (this.currentItemIndex > 0) {
          this.currentItemIndex--
          this.setCurrentItem()
          event.preventDefault()
        } else {
          this.searchInput.nativeElement.focus()
          this.currentItemIndex = -1
        }
      } else if (event.key === 'ArrowRight') {
        this.secondaryButtons.get(this.currentItemIndex).nativeElement.focus()
      } else if (event.key === 'ArrowLeft') {
        this.primaryButtons.get(this.currentItemIndex).nativeElement.focus()
      }
    }
  }

  constructor(
    private searchService: SearchService,
    private router: Router,
    private modalService: NgbModal,
    private documentService: DocumentService,
    private documentListViewService: DocumentListViewService
  ) {
    this.queryDebounce = new Subject<string>()

    this.queryDebounce
      .pipe(
        debounceTime(400),
        distinctUntilChanged(),
        filter((query) => !query?.length || query?.length > 2)
      )
      .subscribe((text) => {
        this.query = text
        if (text) this.search(text)
      })
  }

  private search(query: string) {
    this.loading = true
    this.searchService.globalSearch(query).subscribe((results) => {
      this.searchResults = results
      this.loading = false
      this.resultsDropdown.open()
    })
  }

  public primaryAction(type: string, object: ObjectWithId) {
    this.reset(true)
    let filterRuleType: number
    let editDialogComponent: any
    let size: string = 'md'
    switch (type) {
      case 'document':
        this.router.navigate(['/documents', object.id])
        return
      case 'correspondent':
        filterRuleType = FILTER_HAS_CORRESPONDENT_ANY
        break
      case 'documentType':
        filterRuleType = FILTER_HAS_DOCUMENT_TYPE_ANY
        break
      case 'storagePath':
        filterRuleType = FILTER_HAS_STORAGE_PATH_ANY
        break
      case 'tag':
        filterRuleType = FILTER_HAS_ANY_TAG
        break
      case 'user':
        editDialogComponent = UserEditDialogComponent
        size = 'lg'
        break
      case 'group':
        editDialogComponent = GroupEditDialogComponent
        size = 'lg'
        break
      case 'mailAccount':
        editDialogComponent = MailAccountEditDialogComponent
        size = 'xl'
        break
      case 'mailRule':
        editDialogComponent = MailRuleEditDialogComponent
        size = 'xl'
        break
      case 'customField':
        editDialogComponent = CustomFieldEditDialogComponent
        break
      case 'workflow':
        editDialogComponent = WorkflowEditDialogComponent
        size = 'xl'
        break
    }

    if (filterRuleType) {
      this.documentListViewService.quickFilter([
        { rule_type: filterRuleType, value: object.id.toString() },
      ])
    } else if (editDialogComponent) {
      const modalRef: NgbModalRef = this.modalService.open(
        editDialogComponent,
        { size }
      )
      modalRef.componentInstance.dialogMode = EditDialogMode.EDIT
      modalRef.componentInstance.object = object
    }
  }

  public secondaryAction(type: string, object: ObjectWithId) {
    this.reset(true)
    let editDialogComponent: any
    let size: string = 'md'
    switch (type) {
      case 'document':
        window.open(this.documentService.getDownloadUrl(object.id))
        break
      case 'correspondent':
        editDialogComponent = CorrespondentEditDialogComponent
        break
      case 'documentType':
        editDialogComponent = DocumentTypeEditDialogComponent
        break
      case 'storagePath':
        editDialogComponent = StoragePathEditDialogComponent
        break
      case 'tag':
        editDialogComponent = TagEditDialogComponent
        break
    }

    if (editDialogComponent) {
      const modalRef: NgbModalRef = this.modalService.open(
        editDialogComponent,
        { size }
      )
      modalRef.componentInstance.dialogMode = EditDialogMode.EDIT
      modalRef.componentInstance.object = object
    }
  }

  private reset(close: boolean = false) {
    this.queryDebounce.next(null)
    this.searchResults = null
    this.currentItemIndex = -1
    if (close) {
      this.resultsDropdown.close()
    }
  }

  private setCurrentItem() {
    const item: ElementRef = this.primaryButtons.get(this.currentItemIndex)
    item.nativeElement.focus()
  }

  onItemHover(event: MouseEvent) {
    const item: ElementRef = this.resultItems
      .toArray()
      .find((item) => item.nativeElement === event.currentTarget)
    this.currentItemIndex = this.resultItems.toArray().indexOf(item)
    this.setCurrentItem()
  }

  onButtonHover(event: MouseEvent) {
    ;(event.currentTarget as HTMLElement).focus()
  }

  public searchInputKeyDown(event: KeyboardEvent) {
    if (
      event.key === 'ArrowDown' &&
      this.searchResults &&
      this.resultsDropdown.isOpen()
    ) {
      this.currentItemIndex = 0
      this.setCurrentItem()
    } else if (
      event.key === 'Enter' &&
      this.searchResults?.total === 1 &&
      this.resultsDropdown.isOpen()
    ) {
      this.primaryButtons.first.nativeElement.click()
    } else if (event.key === 'Escape' && !this.resultsDropdown.isOpen()) {
      this.reset(true)
    }
  }

  public onDropdownOpenChange(open: boolean) {
    if (!open) {
      this.reset()
    }
  }
}
