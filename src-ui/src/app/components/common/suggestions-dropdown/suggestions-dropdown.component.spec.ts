import { ComponentFixture, TestBed } from '@angular/core/testing'
import { NgbDropdownModule } from '@ng-bootstrap/ng-bootstrap'
import { NgxBootstrapIconsModule, allIcons } from 'ngx-bootstrap-icons'
import { SuggestionsDropdownComponent } from './suggestions-dropdown.component'

describe('SuggestionsDropdownComponent', () => {
  let component: SuggestionsDropdownComponent
  let fixture: ComponentFixture<SuggestionsDropdownComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [
        NgbDropdownModule,
        NgxBootstrapIconsModule.pick(allIcons),
        SuggestionsDropdownComponent,
      ],
      providers: [],
    })
    fixture = TestBed.createComponent(SuggestionsDropdownComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should exclude suggested storage path names from totalSuggestions', () => {
    fixture.componentRef.setInput('suggestions', {
      suggested_correspondents: ['John Doe'],
      suggested_tags: ['Tag1', 'Tag2'],
      suggested_document_types: ['Type1'],
      suggested_storage_paths: ['Finance/Invoices'],
    })
    expect(component.totalSuggestions).toBe(4)
  })

  it('should count suggestions when a category is absent from the response', () => {
    fixture.componentRef.setInput('suggestions', {
      suggested_tags: ['Tag1'],
    })
    expect(component.totalSuggestions).toBe(1)
  })

  it('should count reused values the document does not have yet', () => {
    fixture.componentRef.setInput('suggestions', {
      tags: [1, 2, 3],
      correspondents: [10],
      document_types: [20],
      suggested_tags: ['NewTag'],
    })
    fixture.componentRef.setInput('appliedTags', [2])
    fixture.componentRef.setInput('appliedDocumentType', 20)

    // tags 1 and 3 are not applied yet, correspondent 10 is not set, tag 2 and
    // document type 20 already are.
    expect(component.reusableSuggestions).toBe(3)
    expect(component.novelSuggestions).toBe(1)
    expect(component.totalSuggestions).toBe(4)
  })

  it('should not count reused values that are already applied', () => {
    fixture.componentRef.setInput('suggestions', {
      tags: [1],
      correspondents: [10],
      document_types: [20],
    })
    fixture.componentRef.setInput('appliedTags', [1])
    fixture.componentRef.setInput('appliedCorrespondent', 10)
    fixture.componentRef.setInput('appliedDocumentType', 20)

    expect(component.totalSuggestions).toBe(0)
  })

  it('should point at the fields when suggestions are all reused', () => {
    // The dropdown lists only values to create, so a response made entirely of
    // reused existing objects used to render as "No novel suggestions".
    fixture.componentRef.setInput('aiEnabled', true)
    fixture.componentRef.setInput('suggestions', {
      tags: [1, 2],
      suggested_tags: [],
      suggested_correspondents: [],
      suggested_document_types: [],
    })
    fixture.detectChanges()
    component.clickSuggest()
    fixture.detectChanges()

    expect(fixture.nativeElement.textContent).toContain(
      '2 existing values suggested below'
    )
    expect(fixture.nativeElement.textContent).not.toContain(
      'No novel suggestions'
    )
  })

  it('should account for reused values alongside values to create', () => {
    // The badge counts both, but only the novel names are listed here, so the
    // dropdown has to say where the rest of the count came from.
    fixture.componentRef.setInput('aiEnabled', true)
    fixture.componentRef.setInput('suggestions', {
      tags: [6, 3],
      suggested_tags: ['Arbitration', 'New York'],
      suggested_correspondents: [],
      suggested_document_types: [],
    })
    fixture.detectChanges()
    component.clickSuggest()
    fixture.detectChanges()

    expect(component.totalSuggestions).toBe(4)
    expect(fixture.nativeElement.textContent).toContain('Arbitration')
    expect(fixture.nativeElement.textContent).toContain(
      '2 existing values suggested below'
    )
  })

  it('should count classic (non-AI) suggestions, which are ids only', () => {
    // /api/documents/{id}/suggestions/ returns only id arrays and no
    // suggested_* keys at all, so every one of its suggestions is a reused
    // existing object - including storage paths.
    fixture.componentRef.setInput('suggestions', {
      correspondents: [4],
      tags: [6, 3],
      document_types: [2],
      storage_paths: [7],
      dates: ['2005-01-01'],
    })

    expect(component.novelSuggestions).toBe(0)
    expect(component.totalSuggestions).toBe(5)

    fixture.componentRef.setInput('appliedStoragePath', 7)
    expect(component.totalSuggestions).toBe(4)
  })

  it('should show when a completed request returned no suggestions', () => {
    fixture.componentRef.setInput('suggestions', {
      correspondents: [],
      tags: [],
      document_types: [],
      storage_paths: [],
      dates: [],
    })
    fixture.detectChanges()

    expect(component.noSuggestions).toBeTruthy()
    expect(fixture.nativeElement.textContent).toContain('No suggestions')
  })

  it('should not show the empty state before a request or with suggestions', () => {
    expect(component.noSuggestions).toBeFalsy()

    fixture.componentRef.setInput('suggestions', {
      correspondents: [],
      tags: [42],
      document_types: [],
      storage_paths: [],
      dates: [],
    })

    expect(component.noSuggestions).toBeFalsy()
  })

  it('should emit getSuggestions when clickSuggest is called and suggestions are null', () => {
    jest.spyOn(component.getSuggestions, 'emit')
    fixture.componentRef.setInput('suggestions', null)
    component.clickSuggest()
    expect(component.getSuggestions.emit).toHaveBeenCalled()
  })

  it('should not emit getSuggestions when disabled', () => {
    jest.spyOn(component.getSuggestions, 'emit')
    fixture.componentRef.setInput('disabled', true)
    fixture.componentRef.setInput('suggestions', null)
    fixture.detectChanges()

    component.clickSuggest()

    expect(component.getSuggestions.emit).not.toHaveBeenCalled()
    expect(fixture.nativeElement.querySelector('button').disabled).toBeTruthy()
  })

  it('should toggle dropdown when clickSuggest is called and suggestions are not null', () => {
    fixture.componentRef.setInput('aiEnabled', true)
    fixture.detectChanges()
    fixture.componentRef.setInput('suggestions', {
      suggested_correspondents: [],
      suggested_tags: [],
      suggested_document_types: [],
    })
    component.clickSuggest()
    expect(component.dropdown.open).toBeTruthy()
    expect(fixture.nativeElement.textContent).toContain('No novel suggestions')
  })
})
