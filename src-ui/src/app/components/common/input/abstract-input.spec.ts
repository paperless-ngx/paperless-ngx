import { Component } from '@angular/core'
import { AbstractInputComponent } from './abstract-input'
import { ComponentFixture, TestBed } from '@angular/core/testing'
import { FormsModule, ReactiveFormsModule } from '@angular/forms'

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
      declarations: [TestComponent],
      providers: [],
      imports: [FormsModule, ReactiveFormsModule],
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
