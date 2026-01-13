import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { TextComponent } from './text.component'

describe('TextComponent', () => {
  let component: TextComponent
  let fixture: ComponentFixture<TextComponent>
  let input: HTMLInputElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [],
      imports: [FormsModule, ReactiveFormsModule, TextComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(TextComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    expect(component.value).toBeUndefined()
    input.value = 'foo'
    input.dispatchEvent(new Event('input'))
    fixture.detectChanges()
    expect(component.value).toBe('foo')
  })

  it('should support suggestion', () => {
    component.value = 'foo'
    component.suggestion = 'foo'
    expect(component.getSuggestion()).toBe('')
    component.value = 'bar'
    expect(component.getSuggestion()).toBe('foo')
    component.applySuggestion()
    fixture.detectChanges()
    expect(component.value).toBe('foo')
  })
})
