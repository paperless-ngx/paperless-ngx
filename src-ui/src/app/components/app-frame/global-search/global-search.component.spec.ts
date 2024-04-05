import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { GlobalSearchComponent } from './global-search.component'
import { of } from 'rxjs'
import { SearchService } from 'src/app/services/rest/search.service'
import { Router } from '@angular/router'
import {
  NgbDropdownModule,
  NgbModal,
  NgbModalModule,
  NgbModalRef,
} from '@ng-bootstrap/ng-bootstrap'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_HAS_STORAGE_PATH_ANY,
  FILTER_HAS_TAGS_ANY,
} from 'src/app/data/filter-rule-type'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { DocumentService } from 'src/app/services/rest/document.service'
import { MailRuleEditDialogComponent } from '../../common/edit-dialog/mail-rule-edit-dialog/mail-rule-edit-dialog.component'
import { MailAccountEditDialogComponent } from '../../common/edit-dialog/mail-account-edit-dialog/mail-account-edit-dialog.component'
import { GroupEditDialogComponent } from '../../common/edit-dialog/group-edit-dialog/group-edit-dialog.component'
import { CustomFieldEditDialogComponent } from '../../common/edit-dialog/custom-field-edit-dialog/custom-field-edit-dialog.component'
import { WorkflowEditDialogComponent } from '../../common/edit-dialog/workflow-edit-dialog/workflow-edit-dialog.component'
import { ElementRef } from '@angular/core'
import { ToastService } from 'src/app/services/toast.service'
import { DataType } from 'src/app/data/datatype'

const searchResults = {
  total: 11,
  documents: [
    {
      id: 1,
      title: 'Test',
      created_at: new Date(),
      updated_at: new Date(),
      document_type: { id: 1, name: 'Test' },
      storage_path: { id: 1, path: 'Test' },
      tags: [],
      correspondents: [],
      custom_fields: [],
    },
  ],
  correspondents: [
    {
      id: 1,
      name: 'TestCorrespondent',
    },
  ],
  document_types: [
    {
      id: 1,
      name: 'TestDocumentType',
    },
  ],
  storage_paths: [
    {
      id: 1,
      name: 'TestStoragePath',
    },
  ],
  tags: [
    {
      id: 1,
      name: 'TestTag',
    },
  ],
  users: [
    {
      id: 1,
      username: 'TestUser',
    },
  ],
  groups: [
    {
      id: 1,
      name: 'TestGroup',
    },
  ],
  mail_accounts: [
    {
      id: 1,
      name: 'TestMailAccount',
    },
  ],
  mail_rules: [
    {
      id: 1,
      name: 'TestMailRule',
    },
  ],
  custom_fields: [
    {
      id: 1,
      name: 'TestCustomField',
    },
  ],
  workflows: [
    {
      id: 1,
      name: 'TestWorkflow',
    },
  ],
}

describe('GlobalSearchComponent', () => {
  let component: GlobalSearchComponent
  let fixture: ComponentFixture<GlobalSearchComponent>
  let searchService: SearchService
  let router: Router
  let modalService: NgbModal
  let documentService: DocumentService
  let documentListViewService: DocumentListViewService
  let toastService: ToastService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [GlobalSearchComponent],
      imports: [
        HttpClientTestingModule,
        NgbModalModule,
        NgbDropdownModule,
        FormsModule,
        ReactiveFormsModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
    }).compileComponents()

    searchService = TestBed.inject(SearchService)
    router = TestBed.inject(Router)
    modalService = TestBed.inject(NgbModal)
    documentService = TestBed.inject(DocumentService)
    documentListViewService = TestBed.inject(DocumentListViewService)
    toastService = TestBed.inject(ToastService)

    fixture = TestBed.createComponent(GlobalSearchComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should handle keyboard nav', () => {
    const focusSpy = jest.spyOn(component.searchInput.nativeElement, 'focus')
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })
    )
    expect(focusSpy).toHaveBeenCalled()
    // coverage
    document.dispatchEvent(
      new KeyboardEvent('keydown', { key: 'k', metaKey: true })
    )

    component.searchResults = searchResults as any
    component.resultsDropdown.open()
    fixture.detectChanges()

    component['currentItemIndex'] = 0
    component['setCurrentItem']()
    const firstItemFocusSpy = jest.spyOn(
      component.primaryButtons.get(1).nativeElement,
      'focus'
    )
    component.dropdownKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowDown' })
    )
    expect(component['currentItemIndex']).toBe(1)
    expect(firstItemFocusSpy).toHaveBeenCalled()

    const secondaryItemFocusSpy = jest.spyOn(
      component.secondaryButtons.get(1).nativeElement,
      'focus'
    )
    component.dropdownKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowRight' })
    )
    expect(secondaryItemFocusSpy).toHaveBeenCalled()

    component.dropdownKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowLeft' })
    )
    expect(firstItemFocusSpy).toHaveBeenCalled()

    const zeroItemSpy = jest.spyOn(
      component.primaryButtons.get(0).nativeElement,
      'focus'
    )
    component.dropdownKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    expect(component['currentItemIndex']).toBe(0)
    expect(zeroItemSpy).toHaveBeenCalled()

    const inputFocusSpy = jest.spyOn(
      component.searchInput.nativeElement,
      'focus'
    )
    component.dropdownKeyDown(new KeyboardEvent('keydown', { key: 'ArrowUp' }))
    expect(component['currentItemIndex']).toBe(-1)
    expect(inputFocusSpy).toHaveBeenCalled()

    component.dropdownKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowDown' })
    )
    component['currentItemIndex'] = searchResults.total - 1
    component['setCurrentItem']()
    component.dropdownKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowDown' })
    )
    expect(component['currentItemIndex']).toBe(-1)

    // Search input

    component.searchInputKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowUp' })
    )
    expect(component['currentItemIndex']).toBe(searchResults.total - 1)

    component.searchInputKeyDown(
      new KeyboardEvent('keydown', { key: 'ArrowDown' })
    )
    expect(component['currentItemIndex']).toBe(0)

    component.searchResults = { total: 1 } as any
    const primaryActionSpy = jest.spyOn(component, 'primaryAction')
    component.searchInputKeyDown(new KeyboardEvent('keydown', { key: 'Enter' }))
    expect(primaryActionSpy).toHaveBeenCalled()

    component.query = 'test'
    const resetSpy = jest.spyOn(GlobalSearchComponent.prototype as any, 'reset')
    component.searchInputKeyDown(
      new KeyboardEvent('keydown', { key: 'Escape' })
    )
    expect(resetSpy).toHaveBeenCalled()

    component.query = ''
    const blurSpy = jest.spyOn(component.searchInput.nativeElement, 'blur')
    component.searchInputKeyDown(
      new KeyboardEvent('keydown', { key: 'Escape' })
    )
    expect(blurSpy).toHaveBeenCalled()
  })

  it('should search on query debounce', fakeAsync(() => {
    const query = 'test'
    const searchSpy = jest.spyOn(searchService, 'globalSearch')
    searchSpy.mockReturnValue(of({} as any))
    const dropdownOpenSpy = jest.spyOn(component.resultsDropdown, 'open')
    component.queryDebounce.next(query)
    tick(401)
    expect(searchSpy).toHaveBeenCalledWith(query)
    expect(dropdownOpenSpy).toHaveBeenCalled()
  }))

  it('should support primary action', () => {
    const object = { id: 1 }
    const routerSpy = jest.spyOn(router, 'navigate')
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    const modalSpy = jest.spyOn(modalService, 'open')

    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))

    component.primaryAction(DataType.Document, object)
    expect(routerSpy).toHaveBeenCalledWith(['/documents', object.id])

    component.primaryAction(DataType.Correspondent, object)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_CORRESPONDENT_ANY, value: object.id.toString() },
    ])

    component.primaryAction(DataType.DocumentType, object)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY, value: object.id.toString() },
    ])

    component.primaryAction(DataType.StoragePath, object)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_STORAGE_PATH_ANY, value: object.id.toString() },
    ])

    component.primaryAction(DataType.Tag, object)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_TAGS_ANY, value: object.id.toString() },
    ])

    component.primaryAction(DataType.User, object)
    expect(modalSpy).toHaveBeenCalledWith(UserEditDialogComponent, {
      size: 'lg',
    })

    component.primaryAction(DataType.Group, object)
    expect(modalSpy).toHaveBeenCalledWith(GroupEditDialogComponent, {
      size: 'lg',
    })

    component.primaryAction(DataType.MailAccount, object)
    expect(modalSpy).toHaveBeenCalledWith(MailAccountEditDialogComponent, {
      size: 'xl',
    })

    component.primaryAction(DataType.MailRule, object)
    expect(modalSpy).toHaveBeenCalledWith(MailRuleEditDialogComponent, {
      size: 'xl',
    })

    component.primaryAction(DataType.CustomField, object)
    expect(modalSpy).toHaveBeenCalledWith(CustomFieldEditDialogComponent, {
      size: 'md',
    })

    component.primaryAction(DataType.Workflow, object)
    expect(modalSpy).toHaveBeenCalledWith(WorkflowEditDialogComponent, {
      size: 'xl',
    })

    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(true)
    expect(toastInfoSpy).toHaveBeenCalled()
  })

  it('should support secondary action', () => {
    const doc = searchResults.documents[0]
    const openSpy = jest.spyOn(window, 'open')
    component.secondaryAction('document', doc)
    expect(openSpy).toHaveBeenCalledWith(documentService.getDownloadUrl(doc.id))

    const correspondent = searchResults.correspondents[0]
    const modalSpy = jest.spyOn(modalService, 'open')

    let modal: NgbModalRef
    modalService.activeInstances.subscribe((m) => (modal = m[m.length - 1]))

    component.secondaryAction(DataType.Correspondent, correspondent)
    expect(modalSpy).toHaveBeenCalledWith(CorrespondentEditDialogComponent, {
      size: 'md',
    })

    component.secondaryAction(
      DataType.DocumentType,
      searchResults.document_types[0]
    )
    expect(modalSpy).toHaveBeenCalledWith(CorrespondentEditDialogComponent, {
      size: 'md',
    })

    component.secondaryAction(
      DataType.StoragePath,
      searchResults.storage_paths[0]
    )
    expect(modalSpy).toHaveBeenCalledWith(CorrespondentEditDialogComponent, {
      size: 'md',
    })

    component.secondaryAction(DataType.Tag, searchResults.tags[0])
    expect(modalSpy).toHaveBeenCalledWith(CorrespondentEditDialogComponent, {
      size: 'md',
    })

    const editDialog = modal.componentInstance as CustomFieldEditDialogComponent
    const toastErrorSpy = jest.spyOn(toastService, 'showError')
    const toastInfoSpy = jest.spyOn(toastService, 'showInfo')

    // fail first
    editDialog.failed.emit({ error: 'error creating item' })
    expect(toastErrorSpy).toHaveBeenCalled()

    // succeed
    editDialog.succeeded.emit(true)
    expect(toastInfoSpy).toHaveBeenCalled()
  })

  it('should support reset', () => {
    const debounce = jest.spyOn(component.queryDebounce, 'next')
    const closeSpy = jest.spyOn(component.resultsDropdown, 'close')
    component['reset'](true)
    expect(debounce).toHaveBeenCalledWith(null)
    expect(component.searchResults).toBeNull()
    expect(component['currentItemIndex']).toBe(-1)
    expect(closeSpy).toHaveBeenCalled()
  })

  it('should support focus current item', () => {
    component.searchResults = searchResults as any
    fixture.detectChanges()
    const focusSpy = jest.spyOn(
      component.primaryButtons.get(0).nativeElement,
      'focus'
    )
    component['currentItemIndex'] = 0
    component['setCurrentItem']()
    expect(focusSpy).toHaveBeenCalled()
  })

  it('should reset on dropdown close', () => {
    const resetSpy = jest.spyOn(GlobalSearchComponent.prototype as any, 'reset')
    component.onDropdownOpenChange(false)
    expect(resetSpy).toHaveBeenCalled()
  })

  it('should focus button on dropdown item hover', () => {
    component.searchResults = searchResults as any
    fixture.detectChanges()
    const item: ElementRef = component.resultItems.first
    const focusSpy = jest.spyOn(
      component.primaryButtons.first.nativeElement,
      'focus'
    )
    component.onItemHover({ currentTarget: item.nativeElement } as any)
    expect(component['currentItemIndex']).toBe(0)
    expect(focusSpy).toHaveBeenCalled()
  })

  it('should focus on button hover', () => {
    const event = { currentTarget: { focus: jest.fn() } }
    const focusSpy = jest.spyOn(event.currentTarget, 'focus')
    component.onButtonHover(event as any)
    expect(focusSpy).toHaveBeenCalled()
  })
})
