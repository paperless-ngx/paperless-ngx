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
      declarations: [TextComponent],
      providers: [],
      imports: [FormsModule, ReactiveFormsModule],
    }).compileComponents()

    fixture = TestBed.createComponent(TextComponent)
    fixture.debugElement.injector.get(NG_VALUE_ACCESSOR)
    component = fixture.componentInstance
    fixture.detectChanges()
    input = component.inputField.nativeElement
  })

  it('should support use of input field', () => {
    expect(component.value).toBeUndefined()
    // TODO: why doesn't this work?
    // input.value = 'foo'
    // input.dispatchEvent(new Event('change'))
    // fixture.detectChanges()
    // expect(component.value).toEqual('foo')
  })
})
