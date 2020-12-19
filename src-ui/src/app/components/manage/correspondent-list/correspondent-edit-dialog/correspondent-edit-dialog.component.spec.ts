import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CorrespondentEditDialogComponent } from './correspondent-edit-dialog.component';

describe('CorrespondentEditDialogComponent', () => {
  let component: CorrespondentEditDialogComponent;
  let fixture: ComponentFixture<CorrespondentEditDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ CorrespondentEditDialogComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(CorrespondentEditDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
