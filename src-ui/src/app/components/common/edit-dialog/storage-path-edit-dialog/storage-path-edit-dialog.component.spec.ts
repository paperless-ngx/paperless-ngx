import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import {
  NgbAccordionButton,
  NgbActiveModal,
  NgbModule,
} from '@ng-bootstrap/ng-bootstrap'
import { NgSelectModule } from '@ng-select/ng-select'
import { IfOwnerDirective } from 'src/app/directives/if-owner.directive'
import { IfPermissionsDirective } from 'src/app/directives/if-permissions.directive'
import { SafeHtmlPipe } from 'src/app/pipes/safehtml.pipe'
import { SettingsService } from 'src/app/services/settings.service'
import { PermissionsFormComponent } from '../../input/permissions/permissions-form/permissions-form.component'
import { SelectComponent } from '../../input/select/select.component'
import { TextComponent } from '../../input/text/text.component'
import { TextAreaComponent } from '../../input/textarea/textarea.component'
import { EditDialogMode } from '../edit-dialog.component'
import { StoragePathEditDialogComponent } from './storage-path-edit-dialog.component'
import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { DocumentService } from 'src/app/services/rest/document.service'
import { of, throwError } from 'rxjs'
import { FILTER_TITLE } from 'src/app/data/filter-rule-type'
import { By } from '@angular/platform-browser'

describe('StoragePathEditDialogComponent', () => {
  let component: StoragePathEditDialogComponent
  let settingsService: SettingsService
  let documentService: DocumentService
  let fixture: ComponentFixture<StoragePathEditDialogComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      declarations: [
        StoragePathEditDialogComponent,
        IfPermissionsDirective,
        IfOwnerDirective,
        SelectComponent,
        TextComponent,
        TextAreaComponent,
        PermissionsFormComponent,
        SafeHtmlPipe,
      ],
      imports: [FormsModule, ReactiveFormsModule, NgSelectModule, NgbModule],
      providers: [
        NgbActiveModal,
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
      ],
    }).compileComponents()

    documentService = TestBed.inject(DocumentService)
    fixture = TestBed.createComponent(StoragePathEditDialogComponent)
    settingsService = TestBed.inject(SettingsService)
    settingsService.currentUser = { id: 99, username: 'user99' }
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should support create and edit modes', () => {
    component.dialogMode = EditDialogMode.CREATE
    const createTitleSpy = jest.spyOn(component, 'getCreateTitle')
    const editTitleSpy = jest.spyOn(component, 'getEditTitle')
    fixture.detectChanges()
    expect(createTitleSpy).toHaveBeenCalled()
    expect(editTitleSpy).not.toHaveBeenCalled()
    component.dialogMode = EditDialogMode.EDIT
    fixture.detectChanges()
    expect(editTitleSpy).toHaveBeenCalled()
  })

  it('should support test path', () => {
    const testSpy = jest.spyOn(
      component['service'] as StoragePathService,
      'testPath'
    )
    testSpy.mockReturnValueOnce(of('test/abc123'))
    component.objectForm.patchValue({ path: 'test/{{title}}' })
    fixture.detectChanges()
    component.testPath({ id: 1 })
    expect(testSpy).toHaveBeenCalledWith('test/{{title}}', 1)
    expect(component.testResult).toBe('test/abc123')
    expect(component.testFailed).toBeFalsy()

    // test failed
    testSpy.mockReturnValueOnce(of(''))
    component.testPath({ id: 1 })
    expect(component.testResult).toBeNull()
    expect(component.testFailed).toBeTruthy()

    component.testPath(null)
    expect(component.testResult).toBeNull()
  })

  it('should compare two documents by id', () => {
    const doc1 = { id: 1 }
    const doc2 = { id: 2 }
    expect(component.compareDocuments(doc1, doc1)).toBeTruthy()
    expect(component.compareDocuments(doc1, doc2)).toBeFalsy()
  })

  it('should use id as trackBy', () => {
    expect(component.trackByFn({ id: 1 })).toBe(1)
  })

  it('should search on select text input', () => {
    fixture.debugElement
      .query(By.directive(NgbAccordionButton))
      .triggerEventHandler('click', null)
    fixture.detectChanges()
    const documents = [
      { id: 1, title: 'foo' },
      { id: 2, title: 'bar' },
    ]
    const listSpy = jest.spyOn(documentService, 'listFiltered')
    listSpy.mockReturnValueOnce(
      of({
        count: 1,
        results: documents[0],
        all: [1],
      } as any)
    )
    component.documentsInput$.next('bar')
    expect(listSpy).toHaveBeenCalledWith(
      1,
      null,
      'created',
      true,
      [{ rule_type: FILTER_TITLE, value: 'bar' }],
      { truncate_content: true }
    )
    listSpy.mockReturnValueOnce(
      of({
        count: 2,
        results: [...documents],
        all: [1, 2],
      } as any)
    )
    component.documentsInput$.next('ba')
    listSpy.mockReturnValueOnce(throwError(() => new Error()))
    component.documentsInput$.next('foo')
  })

  it('should run path test on path change', () => {
    const testSpy = jest.spyOn(component, 'testPath')
    component['testDocument'] = { id: 1 } as any
    component.objectForm.patchValue(
      { path: 'test/{{title}}' },
      { emitEvent: true }
    )
    fixture.detectChanges()
    expect(testSpy).toHaveBeenCalled()
  })
})
