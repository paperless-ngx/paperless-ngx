import { provideHttpClient, withInterceptorsFromDi } from '@angular/common/http'
import { provideHttpClientTesting } from '@angular/common/http/testing'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { provideAnimations } from '@angular/platform-browser/animations'
import { NgbCollapseModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { of } from 'rxjs'
import {
  AISuggestion,
  AISuggestionStatus,
  AISuggestionType,
} from 'src/app/data/ai-suggestion'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { StoragePath } from 'src/app/data/storage-path'
import { Tag } from 'src/app/data/tag'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { CustomFieldsService } from 'src/app/services/rest/custom-fields.service'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { ToastService } from 'src/app/services/toast.service'
import { AiSuggestionsPanelComponent } from './ai-suggestions-panel.component'

const mockTags: Tag[] = [
  { id: 1, name: 'Invoice', colour: '#ff0000', text_colour: '#ffffff' },
  { id: 2, name: 'Receipt', colour: '#00ff00', text_colour: '#000000' },
]

const mockCorrespondents: Correspondent[] = [
  { id: 1, name: 'Acme Corp' },
  { id: 2, name: 'TechStart LLC' },
]

const mockDocumentTypes: DocumentType[] = [
  { id: 1, name: 'Invoice' },
  { id: 2, name: 'Contract' },
]

const mockStoragePaths: StoragePath[] = [
  { id: 1, name: '/invoices', path: '/invoices' },
  { id: 2, name: '/contracts', path: '/contracts' },
]

const mockSuggestions: AISuggestion[] = [
  {
    id: '1',
    type: AISuggestionType.Tag,
    value: 1,
    confidence: 0.85,
    status: AISuggestionStatus.Pending,
  },
  {
    id: '2',
    type: AISuggestionType.Correspondent,
    value: 1,
    confidence: 0.75,
    status: AISuggestionStatus.Pending,
  },
  {
    id: '3',
    type: AISuggestionType.DocumentType,
    value: 1,
    confidence: 0.90,
    status: AISuggestionStatus.Pending,
  },
]

describe('AiSuggestionsPanelComponent', () => {
  let component: AiSuggestionsPanelComponent
  let fixture: ComponentFixture<AiSuggestionsPanelComponent>
  let tagService: TagService
  let correspondentService: CorrespondentService
  let documentTypeService: DocumentTypeService
  let storagePathService: StoragePathService
  let customFieldsService: CustomFieldsService
  let toastService: ToastService

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [
        AiSuggestionsPanelComponent,
        NgbCollapseModule,
        NgxBootstrapIconsModule.pick(allIcons),
      ],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        provideAnimations(),
      ],
    }).compileComponents()

    tagService = TestBed.inject(TagService)
    correspondentService = TestBed.inject(CorrespondentService)
    documentTypeService = TestBed.inject(DocumentTypeService)
    storagePathService = TestBed.inject(StoragePathService)
    customFieldsService = TestBed.inject(CustomFieldsService)
    toastService = TestBed.inject(ToastService)

    jest.spyOn(tagService, 'listAll').mockReturnValue(
      of({
        all: mockTags.map((t) => t.id),
        count: mockTags.length,
        results: mockTags,
      })
    )

    jest.spyOn(correspondentService, 'listAll').mockReturnValue(
      of({
        all: mockCorrespondents.map((c) => c.id),
        count: mockCorrespondents.length,
        results: mockCorrespondents,
      })
    )

    jest.spyOn(documentTypeService, 'listAll').mockReturnValue(
      of({
        all: mockDocumentTypes.map((dt) => dt.id),
        count: mockDocumentTypes.length,
        results: mockDocumentTypes,
      })
    )

    jest.spyOn(storagePathService, 'listAll').mockReturnValue(
      of({
        all: mockStoragePaths.map((sp) => sp.id),
        count: mockStoragePaths.length,
        results: mockStoragePaths,
      })
    )

    jest.spyOn(customFieldsService, 'listAll').mockReturnValue(
      of({
        all: [],
        count: 0,
        results: [],
      })
    )

    fixture = TestBed.createComponent(AiSuggestionsPanelComponent)
    component = fixture.componentInstance
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })

  it('should process suggestions on input change', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    expect(component.pendingSuggestions.length).toBe(3)
    expect(component.appliedCount).toBe(0)
    expect(component.rejectedCount).toBe(0)
  })

  it('should group suggestions by type', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    expect(component.groupedSuggestions.size).toBe(3)
    expect(component.groupedSuggestions.get(AISuggestionType.Tag)?.length).toBe(
      1
    )
    expect(
      component.groupedSuggestions.get(AISuggestionType.Correspondent)?.length
    ).toBe(1)
    expect(
      component.groupedSuggestions.get(AISuggestionType.DocumentType)?.length
    ).toBe(1)
  })

  it('should apply a suggestion', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const applySpy = jest.spyOn(component.apply, 'emit')

    const suggestion = component.pendingSuggestions[0]
    component.applySuggestion(suggestion)

    expect(suggestion.status).toBe(AISuggestionStatus.Applied)
    expect(applySpy).toHaveBeenCalledWith(suggestion)
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should reject a suggestion', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const rejectSpy = jest.spyOn(component.reject, 'emit')

    const suggestion = component.pendingSuggestions[0]
    component.rejectSuggestion(suggestion)

    expect(suggestion.status).toBe(AISuggestionStatus.Rejected)
    expect(rejectSpy).toHaveBeenCalledWith(suggestion)
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should apply all suggestions', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const applySpy = jest.spyOn(component.apply, 'emit')

    component.applyAll()

    expect(applySpy).toHaveBeenCalledTimes(3)
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should reject all suggestions', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    const toastSpy = jest.spyOn(toastService, 'showInfo')
    const rejectSpy = jest.spyOn(component.reject, 'emit')

    component.rejectAll()

    expect(rejectSpy).toHaveBeenCalledTimes(3)
    expect(toastSpy).toHaveBeenCalled()
  })

  it('should return correct confidence class', () => {
    expect(component.getConfidenceClass(0.9)).toBe('confidence-high')
    expect(component.getConfidenceClass(0.7)).toBe('confidence-medium')
    expect(component.getConfidenceClass(0.5)).toBe('confidence-low')
  })

  it('should return correct confidence label', () => {
    expect(component.getConfidenceLabel(0.85)).toContain('85%')
    expect(component.getConfidenceLabel(0.65)).toContain('65%')
    expect(component.getConfidenceLabel(0.45)).toContain('45%')
  })

  it('should toggle collapse', () => {
    expect(component.isCollapsed).toBe(false)
    component.toggleCollapse()
    expect(component.isCollapsed).toBe(true)
    component.toggleCollapse()
    expect(component.isCollapsed).toBe(false)
  })

  it('should respect disabled state', () => {
    component.suggestions = mockSuggestions
    component.disabled = true
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })

    const applySpy = jest.spyOn(component.apply, 'emit')
    const suggestion = component.pendingSuggestions[0]
    component.applySuggestion(suggestion)

    expect(applySpy).not.toHaveBeenCalled()
  })

  it('should not render panel when there are no suggestions', () => {
    component.suggestions = []
    fixture.detectChanges()

    expect(component.hasSuggestions).toBe(false)
  })

  it('should render panel when there are suggestions', () => {
    component.suggestions = mockSuggestions
    component.ngOnChanges({
      suggestions: {
        currentValue: mockSuggestions,
        previousValue: [],
        firstChange: true,
        isFirstChange: () => true,
      },
    })
    fixture.detectChanges()

    expect(component.hasSuggestions).toBe(true)
  })
})
