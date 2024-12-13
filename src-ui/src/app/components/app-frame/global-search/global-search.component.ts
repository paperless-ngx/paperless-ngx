import {
  Component,
  ElementRef,
  OnInit,
  QueryList,
  ViewChild,
  ViewChildren,
} from '@angular/core'
import { Router } from '@angular/router'
import { NgbDropdown, NgbModal, NgbModalRef } from '@ng-bootstrap/ng-bootstrap'
import { Subject, debounceTime, distinctUntilChanged, filter } from 'rxjs'
import { DataType } from 'src/app/data/datatype'
import {
  FILTER_FULLTEXT_QUERY,
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_HAS_STORAGE_PATH_ANY,
  FILTER_HAS_TAGS_ALL,
  FILTER_TITLE_CONTENT,
} from 'src/app/data/filter-rule-type'
import { ObjectWithId } from 'src/app/data/object-with-id'
import { GlobalSearchType, SETTINGS_KEYS } from 'src/app/data/ui-settings'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { HotKeyService } from 'src/app/services/hot-key.service'
import {
  PermissionAction,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import {
  GlobalSearchResult,
  SearchService,
} from 'src/app/services/rest/search.service'
import { SettingsService } from 'src/app/services/settings.service'
import { ToastService } from 'src/app/services/toast.service'
import { paramsFromViewState } from 'src/app/utils/query-params'
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

  get useAdvancedForFullSearch(): boolean {
    return (
      this.settingsService.get(SETTINGS_KEYS.SEARCH_FULL_TYPE) ===
      GlobalSearchType.ADVANCED
    )
  }

  constructor(
    public searchService: SearchService,
    private router: Router,
    private modalService: NgbModal,
    private documentService: DocumentService,
    private documentListViewService: DocumentListViewService,
    private permissionsService: PermissionsService,
    private toastService: ToastService,
    private hotkeyService: HotKeyService,
    private settingsService: SettingsService
  ) {
    this.queryDebounce = new Subject<string>()

    this.queryDebounce
      .pipe(
        debounceTime(400),
        filter((query) => !query?.length || query?.length > 2),
        distinctUntilChanged()
      )
      .subscribe((text) => {
        this.query = text
        if (text) this.search(text)
      })
  }

  public ngOnInit() {
    this.hotkeyService
      .addShortcut({ keys: '/', description: $localize`Global search` })
      .subscribe(() => {
        this.searchInput.nativeElement.focus()
      })
  }

  private search(query: string) {
    this.loading = true
    this.searchService.globalSearch(query.trim()).subscribe((results) => {
      this.searchResults = results
      this.loading = false
      this.resultsDropdown.open()
    })
  }

  public primaryAction(
    type: string,
    object: ObjectWithId,
    event: PointerEvent = null
  ) {
    const newWindow = event?.metaKey || event?.ctrlKey
    this.reset(true)
    let filterRuleType: number
    let editDialogComponent: any
    let size: string = 'md'
    switch (type) {
      case DataType.Document:
        this.navigateOrOpenInNewWindow(['/documents', object.id], newWindow)
        return
      case DataType.SavedView:
        this.navigateOrOpenInNewWindow(['/view', object.id], newWindow)
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
        filterRuleType = FILTER_HAS_TAGS_ALL
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
      let params = paramsFromViewState({
        filterRules: [
          { rule_type: filterRuleType, value: object.id.toString() },
        ],
        currentPage: 1,
        sortField: this.documentListViewService.sortField ?? 'created',
        sortReverse: this.documentListViewService.sortReverse,
      })
      this.navigateOrOpenInNewWindow(['/documents'], newWindow, {
        queryParams: params,
      })
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
    this.query = null
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

  public onItemHover(event: MouseEvent) {
    const item: ElementRef = this.resultItems
      .toArray()
      .find((item) => item.nativeElement === event.currentTarget)
    this.currentItemIndex = this.resultItems.toArray().indexOf(item)
    this.setCurrentItem()
  }

  public onButtonHover(event: MouseEvent) {
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
    } else if (event.key === 'Enter') {
      if (this.searchResults?.total === 1 && this.resultsDropdown.isOpen()) {
        this.primaryButtons.first.nativeElement.click()
        this.searchInput.nativeElement.blur()
      } else if (this.query?.length) {
        this.runFullSearch()
        this.reset(true)
      }
    } else if (event.key === 'Escape' && !this.resultsDropdown.isOpen()) {
      if (this.query?.length) {
        this.reset(true)
      } else {
        this.searchInput.nativeElement.blur()
      }
    }
  }

  public dropdownKeyDown(event: KeyboardEvent) {
    if (
      this.searchResults?.total &&
      this.resultsDropdown.isOpen() &&
      document.activeElement !== this.searchInput.nativeElement
    ) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        event.stopImmediatePropagation()
        if (this.currentItemIndex < this.searchResults.total - 1) {
          this.currentItemIndex++
          this.setCurrentItem()
        } else {
          this.searchInput.nativeElement.focus()
          this.currentItemIndex = -1
        }
      } else if (event.key === 'ArrowUp') {
        event.preventDefault()
        event.stopImmediatePropagation()
        if (this.currentItemIndex > 0) {
          this.currentItemIndex--
          this.setCurrentItem()
        } else {
          this.searchInput.nativeElement.focus()
          this.currentItemIndex = -1
        }
      } else if (event.key === 'ArrowRight') {
        event.preventDefault()
        event.stopImmediatePropagation()
        this.secondaryButtons.get(this.domIndex)?.nativeElement.focus()
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault()
        event.stopImmediatePropagation()
        this.primaryButtons.get(this.domIndex).nativeElement.focus()
      } else if (event.key === 'Escape') {
        event.preventDefault()
        event.stopImmediatePropagation()
        this.reset(true)
        this.searchInput.nativeElement.focus()
      }
    }
  }

  public onButtonKeyDown(event: KeyboardEvent) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.target.dispatchEvent(new MouseEvent('click', { ctrlKey: true }))
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

  public runFullSearch() {
    const ruleType = this.useAdvancedForFullSearch
      ? FILTER_FULLTEXT_QUERY
      : FILTER_TITLE_CONTENT
    this.documentListViewService.quickFilter([
      { rule_type: ruleType, value: this.query },
    ])
    this.reset(true)
  }

  private navigateOrOpenInNewWindow(
    commands: any,
    newWindow: boolean = false,
    extras: Object = {}
  ) {
    if (newWindow) {
      const url = this.router.serializeUrl(
        this.router.createUrlTree(commands, extras)
      )
      window.open(url, '_blank')
    } else {
      this.router.navigate(commands, extras)
    }
  }
}
