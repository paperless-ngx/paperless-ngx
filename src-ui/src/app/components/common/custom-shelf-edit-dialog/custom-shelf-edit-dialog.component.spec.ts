import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CustomShelfEditDialogComponent } from './custom-shelf-edit-dialog.component';

describe('CustomShelfEditDialogComponent', () => {
  let component: CustomShelfEditDialogComponent;
  let fixture: ComponentFixture<CustomShelfEditDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [CustomShelfEditDialogComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(CustomShelfEditDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
