import { ComponentFixture, TestBed } from '@angular/core/testing'
import {
  FormsModule,
  NG_VALUE_ACCESSOR,
  ReactiveFormsModule,
} from '@angular/forms'
import { TextAreaComponent } from './textarea.component'

describe('TextComponent', () => {
  let component: TextAreaComponent
  let fixture: ComponentFixture<TextAreaComponent>
  let input: HTMLTextAreaElement

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [],
      imports: [FormsModule, ReactiveFormsModule, TextAreaComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(TextAreaComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    expect(component.value).toBeUndefined()
  })
})
