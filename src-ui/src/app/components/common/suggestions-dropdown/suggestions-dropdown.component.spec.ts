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

  it('should calculate totalSuggestions', () => {
    component.suggestions = {
      suggested_correspondents: ['John Doe'],
      suggested_tags: ['Tag1', 'Tag2'],
      suggested_document_types: ['Type1'],
    }
    expect(component.totalSuggestions).toBe(4)
  })

  it('should emit getSuggestions when clickSuggest is called and suggestions are null', () => {
    jest.spyOn(component.getSuggestions, 'emit')
    component.suggestions = null
    component.clickSuggest()
    expect(component.getSuggestions.emit).toHaveBeenCalled()
  })

  it('should toggle dropdown when clickSuggest is called and suggestions are not null', () => {
    component.aiEnabled = true
    fixture.detectChanges()
    component.suggestions = {
      suggested_correspondents: [],
      suggested_tags: [],
      suggested_document_types: [],
    }
    component.clickSuggest()
    expect(component.dropdown.open).toBeTruthy()
  })
})
