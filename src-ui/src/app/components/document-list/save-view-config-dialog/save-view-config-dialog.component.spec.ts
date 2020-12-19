import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SaveViewConfigDialogComponent } from './save-view-config-dialog.component';

describe('SaveViewConfigDialogComponent', () => {
  let component: SaveViewConfigDialogComponent;
  let fixture: ComponentFixture<SaveViewConfigDialogComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ SaveViewConfigDialogComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(SaveViewConfigDialogComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
