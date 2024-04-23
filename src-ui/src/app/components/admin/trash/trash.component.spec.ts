import { ComponentFixture, TestBed } from '@angular/core/testing'

import { TrashComponent } from './trash.component'

describe('TrashComponent', () => {
  let component: TrashComponent
  let fixture: ComponentFixture<TrashComponent>

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [TrashComponent],
    }).compileComponents()

    fixture = TestBed.createComponent(TrashComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('should create', () => {
    expect(component).toBeTruthy()
  })
})
