import * as SecureStore from 'expo-secure-store';
import React, { useEffect, useState } from 'react';
import { View, ActivityIndicator, StyleSheet, TouchableOpacity } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { useFonts, Outfit_600SemiBold, Outfit_400Regular } from '@expo-google-fonts/outfit';
import * as SplashScreen from 'expo-splash-screen';
import { NavigationContainer, StackActions } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Ionicons } from '@expo/vector-icons';
import WelcomeScreen from './screens/WelcomeScreen';
import LoginScreen from './screens/LoginScreen';
import Dashboard from './screens/Dashboard';
import Wishlist from './screens/Wishlist';
import Closet from './screens/Closet';
import FootCaptureScreen from './screens/FootCaptureScreen';
import CameraScreen from './screens/CameraScreen';
import ARFootCaptureScreen from './screens/ARFootCaptureScreen';
import ARCameraScreen from './screens/ARCameraScreen';
import ManualMeasurementScreen from './screens/ManualMeasurementScreen';
import MeasurementsScreen from './screens/MeasurementsScreen';
import RecommendationsScreen from './screens/RecommendationsScreen';
import ProfileScreen from './screens/ProfileScreen';
import FeedbackScreen from './screens/feedback';
import { SavedShoesProvider } from './SavedShoesContext';
import { OwnedShoesProvider } from './OwnedShoesContext';
// Keep the splash screen visible while we fetch resources
SplashScreen.preventAutoHideAsync();

const RootStack = createNativeStackNavigator();
const ClosetStack = createNativeStackNavigator();
const RecommendationsStack = createNativeStackNavigator();
const ProfileStack = createNativeStackNavigator();
const Tab = createBottomTabNavigator();

const sharedHeaderOptions = {
  headerStyle: { backgroundColor: '#F5EFE6' },
  headerShadowVisible: false,
  headerTitleStyle: { fontFamily: 'Outfit_600SemiBold' },
  contentStyle: { backgroundColor: '#FCFAF7' },
};

const headerLeftBack = (navigation) => (
  <TouchableOpacity
    onPress={() => navigation.goBack()}
    style={{ paddingHorizontal: 4 }}
    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
  >
    <Ionicons name="chevron-back" size={24} color="#2F2A25" />
  </TouchableOpacity>
);

const headerLeftToWelcome = (navigation) => (
  <TouchableOpacity
    onPress={() => navigation.dispatch(StackActions.popToTop())}
    style={{ paddingHorizontal: 4 }}
    hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
  >
    <Ionicons name="chevron-back" size={24} color="#2F2A25" />
  </TouchableOpacity>
);

function ClosetStackNavigator() {
  return (
    <ClosetStack.Navigator screenOptions={sharedHeaderOptions}>
      <ClosetStack.Screen
        name="ClosetHome"
        component={Dashboard}
        options={{
          title: 'Dashboard',
          headerBackVisible: false,
          headerTitleStyle: { fontFamily: 'Outfit_600SemiBold', fontSize: 24 },
        }}
      />
      <ClosetStack.Screen
        name="SavedShoes"
        component={Wishlist}
        options={({ navigation }) => ({
          title: 'Wishlist',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="OwnedShoes"
        component={Closet}
        options={({ navigation }) => ({
          title: 'My Closet',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="Feedback"
        component={FeedbackScreen}
        options={({ navigation }) => ({
          title: 'Fit Feedback',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="FootCapture"
        component={FootCaptureScreen}
        options={({ navigation }) => ({
          title: 'Capture Foot Photo',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="Camera"
        component={CameraScreen}
        options={({ navigation }) => ({
          title: 'Camera',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="ARFootCapture"
        component={ARFootCaptureScreen}
        options={({ navigation }) => ({
          title: 'Measure with AR',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="ARCamera"
        component={ARCameraScreen}
        options={({ navigation }) => ({
          title: 'AR Camera',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="ManualMeasurement"
        component={ManualMeasurementScreen}
        options={({ navigation }) => ({
          title: 'Manual Measurement',
          headerLeft: () => headerLeftBack(navigation),
        })}
      />
      <ClosetStack.Screen
        name="Measurements"
        component={MeasurementsScreen}
        options={{
          title: 'Your Measurements',
          headerBackVisible: false,
          headerLeft: () => null,
        }}
      />
    </ClosetStack.Navigator>
  );
}

function RecommendationsStackNavigator() {
  return (
    <RecommendationsStack.Navigator screenOptions={sharedHeaderOptions}>
      <RecommendationsStack.Screen
        name="RecommendationsHome"
        component={RecommendationsScreen}
        options={{ title: 'Recommendations' }}
      />
    </RecommendationsStack.Navigator>
  );
}

function ProfileStackNavigator() {
  return (
    <ProfileStack.Navigator screenOptions={sharedHeaderOptions}>
      <ProfileStack.Screen
        name="ProfileHome"
        component={ProfileScreen}
        options={{ title: 'Profile', contentStyle: { backgroundColor: '#F5EFE6' } }}
      />
    </ProfileStack.Navigator>
  );
}

const TAB_BAR_STYLE_VISIBLE = { backgroundColor: '#FFFBF5', borderTopColor: '#E2D4C0' };
const HIDE_TAB_BAR_SCREENS = ['FootCapture', 'Camera', 'ARFootCapture', 'ARCamera', 'Measurements'];

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ navigation }) => {
        const state = navigation.getState();
        const currentTab = state?.routes?.[state.index];
        const stackRoute = currentTab?.name === 'Closet' && currentTab?.state?.routes?.[currentTab.state.index];
        const hideTabBar = stackRoute && HIDE_TAB_BAR_SCREENS.includes(stackRoute.name);
        return {
          headerShown: false,
          sceneStyle: { backgroundColor: '#FCFAF7' },
          tabBarStyle: hideTabBar ? { display: 'none' } : TAB_BAR_STYLE_VISIBLE,
          tabBarActiveTintColor: '#C28A5B',
          tabBarInactiveTintColor: '#6B5F52',
          tabBarLabelStyle: { fontFamily: 'Outfit_600SemiBold', fontSize: 12 },
        };
      }}
    >
      <Tab.Screen
        name="Closet"
        component={ClosetStackNavigator}
        options={{
          tabBarLabel: 'Dashboard',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="file-tray-full" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Recommendations"
        component={RecommendationsStackNavigator}
        options={{
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="sparkles" size={size} color={color} />
          ),
        }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileStackNavigator}
        options={{
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person" size={size} color={color} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}

export default function App() {
  const [fontsLoaded] = useFonts({
    Outfit_600SemiBold,
    Outfit_400Regular,
  });
  const [initialRoute, setInitialRoute] = useState(null);

  useEffect(() => {
    SecureStore.getItemAsync('authToken')
      .then(token => setInitialRoute(token ? 'MainTabs' : 'Welcome'))
      .catch(() => setInitialRoute('Welcome'));
  }, []);

  if (!fontsLoaded || initialRoute === null) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#C28A5B" />
      </View>
    );
  }

  SplashScreen.hideAsync();

  return (
    <OwnedShoesProvider>
      <SavedShoesProvider>
        <NavigationContainer>
        <StatusBar style="dark" />
        <RootStack.Navigator
          initialRouteName={initialRoute}
          screenOptions={sharedHeaderOptions}
        >
        <RootStack.Screen
          name="Welcome"
          component={WelcomeScreen}
          options={{ title: 'Shoe Shopper', headerBackVisible: false }}
        />
        <RootStack.Screen
          name="Login"
          component={LoginScreen}
          options={({ navigation }) => ({
            title: 'Log In',
            headerBackVisible: false,
            headerLeft: () => headerLeftToWelcome(navigation),
          })}
        />
        <RootStack.Screen
          name="MainTabs"
          component={MainTabs}
          options={{ headerShown: false }}
        />
        <RootStack.Screen
          name="FootCapture"
          component={FootCaptureScreen}
          options={({ navigation }) => ({
            title: 'Capture Foot Photo',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="Camera"
          component={CameraScreen}
          options={({ navigation }) => ({
            title: 'Camera',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="ARFootCapture"
          component={ARFootCaptureScreen}
          options={({ navigation }) => ({
            title: 'Measure with AR',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="ARCamera"
          component={ARCameraScreen}
          options={({ navigation }) => ({
            title: 'AR Camera',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        <RootStack.Screen
          name="Measurements"
          component={MeasurementsScreen}
          options={{
            title: 'Your Measurements',
            headerBackVisible: false,
            headerLeft: () => null,
          }}
        />
        <RootStack.Screen
          name="Recommendations"
          component={RecommendationsScreen}
          options={({ navigation }) => ({
            title: 'Recommendations',
            headerLeft: () => headerLeftBack(navigation),
          })}
        />
        </RootStack.Navigator>
        </NavigationContainer>
      </SavedShoesProvider>
    </OwnedShoesProvider>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: '#FFF8F0',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
