import { Component } from '@angular/core'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'
import { AbstractInputComponent } from './abstract-input'

@Component({
  template: `
    <div>
      <input
        #inputField
        type="text"
        class="form-control"
        [class.is-invalid]="error"
        [id]="inputId"
        [(ngModel)]="value"
        (change)="onChange(value)"
        [disabled]="disabled"
      />
    </div>
  `,
  imports: [FormsModule, ReactiveFormsModule],
})
class TestComponent extends AbstractInputComponent<string> {
  constructor() {
    super()
  }
}

describe(`AbstractInputComponent`, () => {
  let component: TestComponent
  let fixture: ComponentFixture<TestComponent>

  beforeEach(async () => {
    TestBed.configureTestingModule({
      providers: [],
      imports: [FormsModule, ReactiveFormsModule, TestComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(TestComponent)
    component = fixture.componentInstance

    fixture.detectChanges()
  })

  it('should assign uuid', () => {
    component.ngOnInit()
    expect(component.inputId).not.toBeUndefined()
  })

  it('should support focus', () => {
    const focusSpy = jest.spyOn(component.inputField.nativeElement, 'focus')
    component.focus()
    expect(focusSpy).toHaveBeenCalled()
  })
})
