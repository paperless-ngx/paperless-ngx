import { ComponentFixture, TestBed } from '@angular/core/testing'

import { ConsmptionTemplatesComponent } from './consmption-templates.component'

describe('ConsmptionTemplatesComponent', () => {
  let component: ConsmptionTemplatesComponent
  let fixture: ComponentFixture<ConsmptionTemplatesComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ConsmptionTemplatesComponent],
    })
    fixture = TestBed.createComponent(ConsmptionTemplatesComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })
})
