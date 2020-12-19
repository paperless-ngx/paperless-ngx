import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SavedViewWidgetComponent } from './saved-view-widget.component';

describe('SavedViewWidgetComponent', () => {
  let component: SavedViewWidgetComponent;
  let fixture: ComponentFixture<SavedViewWidgetComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ SavedViewWidgetComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(SavedViewWidgetComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
