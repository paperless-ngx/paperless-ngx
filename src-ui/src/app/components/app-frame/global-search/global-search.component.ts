import {
  Component,
  ViewChild,
  ElementRef,
  ViewChildren,
  QueryList,
  OnInit,
} from '@angular/core'
import { Router } from '@angular/router'
import { NgbDropdown, NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { Subject, debounceTime, distinctUntilChanged, filter, map } from 'rxjs'
import {
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_HAS_STORAGE_PATH_ANY,
  FILTER_HAS_TAGS_ANY,
} from 'src/app/data/filter-rule-type'
import { DataType } from 'src/app/data/datatype'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import {
  PermissionsService,
  PermissionAction,
} from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import {
  GlobalSearchResult,
  SearchService,
} from 'src/app/services/rest/search.service'
import { ToastService } from 'src/app/services/toast.service'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { DocumentTypeEditDialogComponent } from '../../common/edit-dialog/document-type-edit-dialog/document-type-edit-dialog.component'
import { EditDialogMode } from '../../common/edit-dialog/edit-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { MailAccountEditDialogComponent } from '../../common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { MailRuleEditDialogComponent } from '../../common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { StoragePathEditDialogComponent } from '../../common/edit-dialog/storage-path-edit-dialog/storage-path-edit-dialog.component'
import { TagEditDialogComponent } from '../../common/edit-dialog/tag-edit-dialog/tag-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { WorkflowEditDialogComponent } from '../../common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { HotKeyService } from 'src/app/services/hot-key.service'

@Component({
  selector: 'pngx-global-search',
  templateUrl: './global-search.component.html',
  styleUrl: './global-search.component.scss',
})
export class GlobalSearchComponent implements OnInit {
  public DataType = DataType
  public query: string
  public queryDebounce: Subject<string>
  public searchResults: GlobalSearchResult
  private currentItemIndex: number = -1
  private domIndex: number = -1
  public loading: boolean = false

  @ViewChild('searchInput') searchInput: ElementRef
  @ViewChild('resultsDropdown') resultsDropdown: NgbDropdown
  @ViewChildren('resultItem') resultItems: QueryList<ElementRef>
  @ViewChildren('primaryButton') primaryButtons: QueryList<ElementRef>
  @ViewChildren('secondaryButton') secondaryButtons: QueryList<ElementRef>

  constructor(
    private searchService: SearchService,
    private router: Router,
    private modalService: NgbModal,
    private documentService: DocumentService,
    private documentListViewService: DocumentListViewService,
    private permissionsService: PermissionsService,
    private toastService: ToastService,
    private hotkeyService: HotKeyService
  ) {
    this.queryDebounce = new Subject<string>()

    this.queryDebounce
      .pipe(
        debounceTime(400),
        map((query) => query?.trim()),
        filter((query) => !query?.length || query?.length > 2),
        distinctUntilChanged()
      )
      .subscribe((text) => {
        this.query = text
        if (text) this.search(text)
      })
  }

  ngOnInit() {
    this.hotkeyService
      .addShortcut({ keys: '/', description: $localize`Global search` })
      .subscribe(() => {
        this.searchInput.nativeElement.focus()
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
      case DataType.Document:
        this.router.navigate(['/documents', object.id])
        return
      case DataType.Correspondent:
        filterRuleType = FILTER_HAS_CORRESPONDENT_ANY
        break
      case DataType.DocumentType:
        filterRuleType = FILTER_HAS_DOCUMENT_TYPE_ANY
        break
      case DataType.StoragePath:
        filterRuleType = FILTER_HAS_STORAGE_PATH_ANY
        break
      case DataType.Tag:
        filterRuleType = FILTER_HAS_TAGS_ANY
        break
      case DataType.User:
        editDialogComponent = UserEditDialogComponent
        size = 'lg'
        break
      case DataType.Group:
        editDialogComponent = GroupEditDialogComponent
        size = 'lg'
        break
      case DataType.MailAccount:
        editDialogComponent = MailAccountEditDialogComponent
        size = 'xl'
        break
      case DataType.MailRule:
        editDialogComponent = MailRuleEditDialogComponent
        size = 'xl'
        break
      case DataType.CustomField:
        editDialogComponent = CustomFieldEditDialogComponent
        break
      case DataType.Workflow:
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
      modalRef.componentInstance.succeeded.subscribe(() => {
        this.toastService.showInfo($localize`Successfully updated object.`)
      })
      modalRef.componentInstance.failed.subscribe((e) => {
        this.toastService.showError($localize`Error occurred saving object.`, e)
      })
    }
  }

  public secondaryAction(type: string, object: ObjectWithId) {
    this.reset(true)
    let editDialogComponent: any
    let size: string = 'md'
    switch (type) {
      case DataType.Document:
        window.open(this.documentService.getDownloadUrl(object.id))
        break
      case DataType.Correspondent:
        editDialogComponent = CorrespondentEditDialogComponent
        break
      case DataType.DocumentType:
        editDialogComponent = DocumentTypeEditDialogComponent
        break
      case DataType.StoragePath:
        editDialogComponent = StoragePathEditDialogComponent
        break
      case DataType.Tag:
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
      modalRef.componentInstance.succeeded.subscribe(() => {
        this.toastService.showInfo($localize`Successfully updated object.`)
      })
      modalRef.componentInstance.failed.subscribe((e) => {
        this.toastService.showError($localize`Error occurred saving object.`, e)
      })
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
    // QueryLists do not always reflect the current DOM order, so we need to find the actual element
    // Yes, using some vanilla JS
    const result: HTMLElement = this.resultItems.first.nativeElement.parentNode
      .querySelectorAll('.dropdown-item')
      .item(this.currentItemIndex)
    this.domIndex = this.resultItems
      .toArray()
      .indexOf(this.resultItems.find((item) => item.nativeElement === result))
    const item: ElementRef = this.primaryButtons.get(this.domIndex)
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
      this.searchResults?.total &&
      this.resultsDropdown.isOpen()
    ) {
      event.preventDefault()
      this.currentItemIndex = 0
      this.setCurrentItem()
    } else if (
      event.key === 'ArrowUp' &&
      this.searchResults?.total &&
      this.resultsDropdown.isOpen()
    ) {
      event.preventDefault()
      this.currentItemIndex = this.searchResults.total - 1
      this.setCurrentItem()
    } else if (
      event.key === 'Enter' &&
      this.searchResults?.total === 1 &&
      this.resultsDropdown.isOpen()
    ) {
      this.primaryButtons.first.nativeElement.click()
      this.searchInput.nativeElement.blur()
    } else if (event.key === 'Escape' && !this.resultsDropdown.isOpen()) {
      if (this.query?.length) {
        this.reset(true)
      } else {
        this.searchInput.nativeElement.blur()
      }
    }
  }

  dropdownKeyDown(event: KeyboardEvent) {
    if (
      this.searchResults?.total &&
      this.resultsDropdown.isOpen() &&
      document.activeElement !== this.searchInput.nativeElement
    ) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        if (this.currentItemIndex < this.searchResults.total - 1) {
          this.currentItemIndex++
          this.setCurrentItem()
        } else {
          this.searchInput.nativeElement.focus()
          this.currentItemIndex = -1
        }
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        if (this.currentItemIndex > 0) {
          this.currentItemIndex--
          this.setCurrentItem()
        } else {
          this.searchInput.nativeElement.focus()
          this.currentItemIndex = -1
        }
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        this.secondaryButtons.get(this.domIndex)?.nativeElement.focus()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        this.primaryButtons.get(this.domIndex).nativeElement.focus()
      }
    }
  }

  public onDropdownOpenChange(open: boolean) {
    if (!open) {
      this.reset()
    }
  }

  public disablePrimaryButton(type: DataType, object: ObjectWithId): boolean {
    if (
      [
        DataType.Workflow,
        DataType.CustomField,
        DataType.Group,
        DataType.User,
      ].includes(type)
    ) {
      return !this.permissionsService.currentUserHasObjectPermissions(
        PermissionAction.Change,
        object
      )
    }

    return false
  }

  public disableSecondaryButton(type: DataType, object: ObjectWithId): boolean {
    if (DataType.Document === type) {
      return false
    }

    return !this.permissionsService.currentUserHasObjectPermissions(
      PermissionAction.Change,
      object
    )
  }
}
