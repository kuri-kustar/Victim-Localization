#include "victim_localization/view_evaluator_log_reward.h"

view_evaluator_log_reward::view_evaluator_log_reward():
  view_evaluator_base() //Call base class constructor
{
}
double view_evaluator_log_reward::calculateUtility(geometry_msgs::Pose p, Victim_Map_Base *mapping_module){

  grid_map::GridMap temp_Map;

  mapping_module->raytracing_->Initiate(false);

  temp_Map=mapping_module->raytracing_->Generate_2D_Safe_Plane(p,true,true);

  double Info_view=0;

  for (grid_map::GridMapIterator iterator(mapping_module->map); !iterator.isPastEnd(); ++iterator) {
    Position position;
    Index index=*iterator;
    mapping_module->map.getPosition(index, position);
    if(!temp_Map.isInside(position)) continue;

    if(temp_Map.atPosition("temp", position)==0){
      double curr_pro= mapping_module->map.at(mapping_module->getlayer_name(),index);
       Info_view+=-log(1-curr_pro);
  }
}
  return Info_view;
}
std::string view_evaluator_log_reward::getMethodName()
{
  return "IG log";
}







