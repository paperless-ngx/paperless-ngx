import {
  ComponentFixture,
  TestBed,
  fakeAsync,
  tick,
} from '@angular/core/testing'
import { GlobalSearchComponent } from './global-search.component'
import { Subject, of } from 'rxjs'
import { SearchService } from 'src/app/services/rest/search.service'
import { Router } from '@angular/router'
import {
  NgbDropdownModule,
  NgbModal,
  NgbModalModule,
} from '@ng-bootstrap/ng-bootstrap'
import { CorrespondentEditDialogComponent } from '../../common/edit-dialog/correspondent-edit-dialog/correspondent-edit-dialog.component'
import { UserEditDialogComponent } from '../../common/edit-dialog/user-edit-dialog/user-edit-dialog.component'
import { DocumentListViewService } from 'src/app/services/document-list-view.service'
import { HttpClient } from '@angular/common/http'
import { HttpClientTestingModule } from '@angular/common/http/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { FILTER_HAS_CORRESPONDENT_ANY } from 'src/app/data/filter-rule-type'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { DocumentService } from 'src/app/services/rest/document.service'

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
      path: 'TestStoragePath',
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

    fixture = TestBed.createComponent(GlobalSearchComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should initialize properties', () => {
    expect(component.query).toBeUndefined()
    expect(component.queryDebounce).toBeInstanceOf(Subject)
    expect(component.searchResults).toBeUndefined()
    expect(component['currentItemIndex']).toBeUndefined()
  })

  it('should handle keyboard events', () => {
    const focusSpy = jest.spyOn(component.searchInput.nativeElement, 'focus')
    component.handleKeyboardEvent(
      new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })
    )
    expect(focusSpy).toHaveBeenCalled()
    // coverage
    component.handleKeyboardEvent(
      new KeyboardEvent('keydown', { key: 'k', metaKey: true })
    )

    component.searchResults = searchResults as any
    component.resultsDropdown.open()
    fixture.detectChanges()

    component['currentItemIndex'] = 0
    const firstItemFocusSpy = jest.spyOn(
      component.resultItems.get(1).nativeElement,
      'focus'
    )
    component.handleKeyboardEvent(
      new KeyboardEvent('keydown', { key: 'ArrowDown' })
    )
    expect(component['currentItemIndex']).toBe(1)
    expect(firstItemFocusSpy).toHaveBeenCalled()

    const zeroItemSpy = jest.spyOn(
      component.resultItems.get(0).nativeElement,
      'focus'
    )
    component.handleKeyboardEvent(
      new KeyboardEvent('keydown', { key: 'ArrowUp' })
    )
    expect(component['currentItemIndex']).toBe(0)
    expect(zeroItemSpy).toHaveBeenCalled()

    const actionSpy = jest.spyOn(component, 'primaryAction')
    component.handleKeyboardEvent(
      new KeyboardEvent('keydown', { key: 'Enter' })
    )
    expect(actionSpy).toHaveBeenCalled()
  })

  it('should search', fakeAsync(() => {
    const query = 'test'
    const searchSpy = jest.spyOn(searchService, 'globalSearch')
    searchSpy.mockReturnValue(of({} as any))
    const dropdownOpenSpy = jest.spyOn(component.resultsDropdown, 'open')
    component.queryDebounce.next(query)
    tick(401)
    expect(searchSpy).toHaveBeenCalledWith(query)
    expect(dropdownOpenSpy).toHaveBeenCalled()
  }))

  it('should perform primary action', () => {
    const object = { id: 1 }
    const routerSpy = jest.spyOn(router, 'navigate')
    const qfSpy = jest.spyOn(documentListViewService, 'quickFilter')
    const modalSpy = jest.spyOn(modalService, 'open')

    component.primaryAction('document', object)
    expect(routerSpy).toHaveBeenCalledWith(['/documents', object.id])

    component.primaryAction('correspondent', object)
    expect(qfSpy).toHaveBeenCalledWith([
      { rule_type: FILTER_HAS_CORRESPONDENT_ANY, value: object.id.toString() },
    ])

    component.primaryAction('user', object)
    expect(modalSpy).toHaveBeenCalledWith(UserEditDialogComponent, {
      size: 'lg',
    })
  })

  it('should perform secondary action', () => {
    const doc = searchResults.documents[0]
    const routerSpy = jest.spyOn(router, 'navigate')
    component.secondaryAction('document', doc)
    expect(routerSpy).toHaveBeenCalledWith(
      [documentService.getDownloadUrl(doc.id)],
      { skipLocationChange: true }
    )

    const correspondent = searchResults.correspondents[0]
    const modalSpy = jest.spyOn(modalService, 'open')
    component.secondaryAction('correspondent', correspondent)
    expect(modalSpy).toHaveBeenCalledWith(CorrespondentEditDialogComponent, {
      size: 'lg',
    })
  })

  // it('should reset', () => {
  //   jest.spyOn(component.queryDebounce, 'next');
  //   jest.spyOn(component.resultsDropdown, 'close');
  //   component.reset();
  //   expect(component.queryDebounce.next).toHaveBeenCalledWith('');
  //   expect(component.searchResults).toBeNull();
  //   expect(component['currentItemIndex']).toBeUndefined();
  //   expect(component.resultsDropdown.close).toHaveBeenCalled();
  // });

  // it('should set current item', () => {
  //   jest.spyOn(component.resultItems.get(0).nativeElement, 'focus');
  //   component.currentItemIndex = 0;
  //   component.setCurrentItem();
  //   expect(component.resultItems.get(0).nativeElement.focus).toHaveBeenCalled();
  // });

  // it('should handle search input keydown', () => {
  //   jest.spyOn(component.resultItems.first.nativeElement, 'click');
  //   component.searchResults = { total: 1 };
  //   component.resultsDropdown = { isOpen: () => true };
  //   component.searchInputKeyDown(new KeyboardEvent('keydown', { key: 'ArrowDown' }));
  //   expect(component.currentItemIndex).toBe(0);
  //   expect(component.resultItems.first.nativeElement.focus).toHaveBeenCalled();

  //   component.searchInputKeyDown(new KeyboardEvent('keydown', { key: 'Enter' }));
  //   expect(component.resultItems.first.nativeElement.click).toHaveBeenCalled();
  // });

  // it('should handle dropdown open change', () => {
  //   jest.spyOn(component, 'reset');
  //   component.onDropdownOpenChange(false);
  //   expect(component.reset).toHaveBeenCalled();
  // });
})
