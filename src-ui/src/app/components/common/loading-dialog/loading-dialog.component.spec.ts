import { ComponentFixture, TestBed } from '@angular/core/testing'

import { LoadingDialogComponent } from './loading-dialog.component'

describe('LoadingDialogComponent', () => {
  let component: LoadingDialogComponent
  let fixture: ComponentFixture<LoadingDialogComponent>

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [LoadingDialogComponent],
    })
    fixture = TestBed.createComponent(LoadingDialogComponent)
    component = fixture.componentInstance
    fixture.detectChanges()
  })

  it('needs tests', () => {
    expect(false).toBeTruthy()
  })
})
